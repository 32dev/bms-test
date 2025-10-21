from mido import MidiFile
from pydub import AudioSegment
import os
import re

# === 설정 ===
midi_files = ["input1.mid", "input2.mid", "input3.mid"]
wav_files = ["input1.wav", "input2.wav", "input3.wav"]
output_dir = "notes"
bms_path = "output.bms"
bpm_default = 120
division = 48       # 한 마디 분할 수
base_lane = 11      # 백그라운드 레인 시작

os.makedirs(output_dir, exist_ok=True)

# --- BMS 초기화 ---
if not os.path.exists(bms_path):
    print("⚙️ output.bms 없음 → 새로 생성")
    header = [
        "*---------------------- HEADER FIELD",
        "#PLAYER 1",
        "#GENRE AUTO_MERGE",
        "#TITLE COMBINED MIDI",
        "#ARTIST AI",
        f"#BPM {bpm_default}",
        "#PLAYLEVEL 1",
        "#RANK 2",
        "#LNTYPE 0",  # LN 사용 안함
        "*---------------------- MAIN DATA FIELD"
    ]
    with open(bms_path, "w", encoding="utf-8") as f:
        f.write("\n".join(header))
else:
    print("📄 기존 output.bms 존재 → 병합")

# --- 기존 BMS 읽기 ---
with open(bms_path, "r", encoding="utf-8") as f:
    bms_lines = f.read().splitlines()

# 기존 WAV 최대 인덱스
wav_ids = [int(m.group(1)) for line in bms_lines if (m := re.match(r"#WAV(\d{2})", line))]
next_wav_index = (max(wav_ids) + 1) if wav_ids else 1
print(f"🎧 WAV 시작 인덱스: {next_wav_index:02}")

# 기존 measure_data 초기화
measure_data = {}
for line in bms_lines:
    m = re.match(r"#(\d{3})(\d{2}):(.*)", line)
    if m:
        measure = int(m.group(1))
        channel = m.group(2)
        data = list(re.findall("..", m.group(3)))
        measure_data.setdefault(measure, {})[channel] = data

# --- MIDI + WAV 병합 ---
for idx, (midi_path, wav_path) in enumerate(zip(midi_files, wav_files)):
    if not os.path.exists(midi_path) or not os.path.exists(wav_path):
        print(f"⚠️ {midi_path} 또는 {wav_path} 없음 → 건너뜀")
        continue

    lane_channel = f"{base_lane + idx:02}"  # ex: 11,12,13
    print(f"\n🎼 {midi_path} → 채널 {lane_channel} 병합 중...")

    mid = MidiFile(midi_path)
    ticks_per_beat = mid.ticks_per_beat
    tick_to_sec = lambda t: (t / ticks_per_beat) * (60 / bpm_default)
    audio = AudioSegment.from_file(wav_path)

    # --- MIDI note 추출 ---
    notes = []
    for track in mid.tracks:
        current_tick = 0
        active_notes = {}
        for msg in track:
            current_tick += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                active_notes[msg.note] = current_tick
            elif (msg.type == "note_on" and msg.velocity == 0) or msg.type == "note_off":
                if msg.note in active_notes:
                    start_tick = active_notes[msg.note]
                    end_tick = current_tick
                    notes.append((tick_to_sec(start_tick), tick_to_sec(end_tick), msg.note))
                    del active_notes[msg.note]

    notes.sort(key=lambda x: x[0])
    print(f"🎹 노트 {len(notes)}개 감지")

    # --- WAV 추출 및 중복 방지 ---
    note_map = {}  # (note, 길이) -> WAV 번호
    event_list = []

    for start_sec, end_sec, note in notes:
        start_ms = int(start_sec * 1000)
        end_ms = int(end_sec * 1000)
        length_ms = end_ms - start_ms

        key = (note, length_ms)
        if key not in note_map:
            filename = os.path.join(output_dir, f"note_{next_wav_index:02}.wav")
            segment = audio[start_ms:end_ms]
            segment.export(filename, format="wav")
            note_map[key] = next_wav_index
            next_wav_index += 1

        event_list.append((start_sec, end_sec, note_map[key]))

    # --- WAV 등록 ---
    insert_index = next((i for i, l in enumerate(bms_lines) if l.startswith("*---------------------- MAIN DATA FIELD")), len(bms_lines))
    for (note, length), idxnum in sorted(note_map.items(), key=lambda x: x[1]):
        bms_lines.insert(insert_index, f"#WAV{idxnum:02} {os.path.basename(output_dir)}/note_{idxnum:02}.wav")

    # --- 마디별 배치 ---
    bar_duration = (60 / bpm_default) * 4

    for start_sec, end_sec, wav_id in event_list:
        start_measure = int(start_sec // bar_duration)
        end_measure = int(end_sec // bar_duration)
        start_div = int((start_sec % bar_duration) / bar_duration * division)
        end_div = int((end_sec % bar_duration) / bar_duration * division)

        measure_counter = start_measure
        pos_counter = start_div

        while (measure_counter < end_measure) or (measure_counter == end_measure and pos_counter <= end_div):
            if measure_counter not in measure_data:
                measure_data[measure_counter] = {}
            if lane_channel not in measure_data[measure_counter]:
                measure_data[measure_counter][lane_channel] = ["00"] * division

            measure_data[measure_counter][lane_channel][pos_counter] = f"{wav_id:02}"

            pos_counter += 1
            if pos_counter >= division:
                pos_counter = 0
                measure_counter += 1

    print(f"✅ {midi_path} 완료 (채널 {lane_channel}, WAV {len(note_map)}개)")

# --- MAIN DATA 재구성 ---
main_data = ["*---------------------- MAIN DATA FIELD"]
for measure in sorted(measure_data.keys()):
    for channel in sorted(measure_data[measure].keys()):
        data = "".join(measure_data[measure][channel])
        main_data.append(f"#{measure:03}{channel}:{data}")

# --- BMS 저장 ---
with open(bms_path, "w", encoding="utf-8") as f:
    for line in bms_lines:
        if not line.startswith("#") or not re.match(r"#\d{3}\d{2}:", line):
            f.write(line + "\n")
    f.write("\n".join(main_data))

print("\n🎉 모든 MIDI 병합 완료 (MIDI 길이 기준, WAV 분할 배치)")
print(f"📄 최종 BMS: {bms_path}")
