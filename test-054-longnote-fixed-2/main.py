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
division = 16                # 마디 안 분할 수
min_length_ms = 30           # 단타 최소 길이
longnote_threshold_ms = 300  # 롱노트 기준
base_lane = 11               # 첫 번째 MIDI의 채널

os.makedirs(output_dir, exist_ok=True)

# --- BMS 파일 초기화 ---
if not os.path.exists(bms_path):
    print("⚙️ output.bms 없음 → 새로 생성합니다.")
    header = [
        "*---------------------- HEADER FIELD",
        "#PLAYER 1",
        "#GENRE AUTO_MERGE",
        "#TITLE COMBINED MIDI",
        "#ARTIST AI",
        f"#BPM {bpm_default}",
        "#PLAYLEVEL 1",
        "#RANK 2",
        "#LNTYPE 1",
        "*---------------------- MAIN DATA FIELD"
    ]
    with open(bms_path, "w", encoding="utf-8") as f:
        f.write("\n".join(header))
else:
    print("📄 기존 output.bms 존재 → 병합 진행")

# --- 기존 BMS 데이터 읽기 ---
with open(bms_path, "r", encoding="utf-8") as f:
    bms_lines = f.read().splitlines()

# 기존 WAV 최대 인덱스 계산
wav_ids = [int(m.group(1)) for line in bms_lines if (m := re.match(r"#WAV(\d{2})", line))]
next_wav_index = (max(wav_ids) + 1) if wav_ids else 1
print(f"🎧 기존 WAV 인덱스 시작: {next_wav_index:02}")

# 기존 measure_data 구조 초기화
measure_data = {}
for line in bms_lines:
    m = re.match(r"#(\d{3})(\d{2}):(.*)", line)
    if m:
        measure = int(m.group(1))
        channel = m.group(2)
        data = list(re.findall("..", m.group(3)))
        measure_data.setdefault(measure, {})[channel] = data

# --- 병합 루프 (MIDI + WAV + 레인 매핑) ---
for idx, (midi_path, wav_path) in enumerate(zip(midi_files, wav_files)):
    if not os.path.exists(midi_path) or not os.path.exists(wav_path):
        print(f"⚠️ {midi_path} 또는 {wav_path} 없음 → 건너뜀")
        continue

    lane_channel = f"{base_lane + idx:02}"  # ex: 11, 12, 13
    print(f"\n🎼 {midi_path} → 채널 {lane_channel} 병합 중...")

    mid = MidiFile(midi_path)
    ticks_per_beat = mid.ticks_per_beat
    tick_to_sec = lambda t: (t / ticks_per_beat) * (60 / bpm_default)
    audio = AudioSegment.from_file(wav_path)

    # --- MIDI에서 노트 추출 ---
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
                    if end_tick > start_tick:
                        notes.append((tick_to_sec(start_tick), tick_to_sec(end_tick), msg.note))
                    del active_notes[msg.note]

    notes.sort(key=lambda x: x[0])
    print(f"🎹 노트 {len(notes)}개 감지됨")

    # --- 노트별 WAV 생성 ---
    note_map = {}
    event_list = []
    for start_sec, end_sec, note in notes:
        start_ms = int(start_sec * 1000)
        end_ms = int(end_sec * 1000)
        length_ms = end_ms - start_ms
        if length_ms < min_length_ms:
            continue

        key = (note, length_ms)
        if key not in note_map:
            filename = os.path.join(output_dir, f"note_{next_wav_index:02}.wav")
            segment = audio[start_ms:end_ms]
            segment.export(filename, format="wav")
            note_map[key] = next_wav_index
            next_wav_index += 1

        event_list.append((start_sec, end_sec, note_map[key], length_ms))

    # --- WAV 등록 ---
    insert_index = next((i for i, l in enumerate(bms_lines) if l.startswith("*---------------------- MAIN DATA FIELD")), len(bms_lines))
    for (note, length), idxnum in sorted(note_map.items(), key=lambda x: x[1]):
        bms_lines.insert(insert_index, f"#WAV{idxnum:02} {os.path.basename(output_dir)}/note_{idxnum:02}.wav")

    # --- 마디별/레인별 배치 ---
    bar_duration = (60 / bpm_default) * 4

    for start_sec, end_sec, wav_id, length_ms in event_list:
        start_measure = int(start_sec // bar_duration)
        start_pos = int(((start_sec % bar_duration) / bar_duration) * division)
        start_pos = min(start_pos, division - 1)

        end_measure = int(end_sec // bar_duration)
        end_pos = int(((end_sec % bar_duration) / bar_duration) * division)
        end_pos = min(end_pos, division - 1)

        # --- 롱노트 처리: 마디 전체 채우기 ---
        if length_ms >= longnote_threshold_ms:
            for measure in range(start_measure, end_measure + 1):
                if measure not in measure_data:
                    measure_data[measure] = {}
                if lane_channel not in measure_data[measure]:
                    measure_data[measure][lane_channel] = ["00"] * division

                if measure == start_measure:
                    idx_start = start_pos
                else:
                    idx_start = 0
                if measure == end_measure:
                    idx_end = end_pos
                else:
                    idx_end = division - 1

                for i in range(idx_start, idx_end + 1):
                    cell = measure_data[measure][lane_channel][i]
                    measure_data[measure][lane_channel][i] = f"{wav_id:02}" if cell == "00" else cell + f"{wav_id:02}"
        else:
            # 단타 노트
            if start_measure not in measure_data:
                measure_data[start_measure] = {}
            if lane_channel not in measure_data[start_measure]:
                measure_data[start_measure][lane_channel] = ["00"] * division
            cell = measure_data[start_measure][lane_channel][start_pos]
            measure_data[start_measure][lane_channel][start_pos] = f"{wav_id:02}" if cell == "00" else cell + f"{wav_id:02}"

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

print("\n🎉 모든 MIDI 병합 완료 (롱노트 마디 넘김 처리 포함)")
print(f"📄 최종 BMS 파일: {bms_path}")
