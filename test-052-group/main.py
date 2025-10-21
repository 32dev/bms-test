from mido import MidiFile
from pydub import AudioSegment
import os
import re

# === 설정 ===
midi_files = ["input.mid", "input2.mid", "input3.mid"]
wav_files = ["input.wav", "input2.wav", "input3.wav"]
lanes = ["11", "12", "13"]  # 각 파일별 레인 채널 번호
output_dir = "notes"
bms_path = "output.bms"
bpm_default = 120
division = 16
min_length_ms = 30
longnote_threshold_ms = 300

os.makedirs(output_dir, exist_ok=True)

# --- BMS 초기화 ---
if not os.path.exists(bms_path):
    print("⚙️ 기존 output.bms 없음 → 새로 생성합니다.")
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
    print("📄 기존 output.bms 발견 → 이어서 병합합니다.")

# --- 기존 BMS 읽기 ---
with open(bms_path, "r", encoding="utf-8") as f:
    bms_lines = f.read().splitlines()

# 기존 WAV 인덱스 최대값 찾기
wav_ids = [int(m.group(1)) for line in bms_lines if (m := re.match(r"#WAV(\d{2})", line))]
next_wav_index = (max(wav_ids) + 1) if wav_ids else 1

# 기존 마디 데이터 {measure: {channel: [data]}}
measure_data = {}
for line in bms_lines:
    m = re.match(r"#(\d{3})(\d{2}):(.*)", line)
    if m:
        measure = int(m.group(1))
        channel = m.group(2)
        data = m.group(3)
        if measure not in measure_data:
            measure_data[measure] = {}
        measure_data[measure][channel] = list(re.findall("..", data))

print(f"🎧 기존 WAV 최대 인덱스: {next_wav_index-1:02}")

# --- 병합 루프 ---
for midi_path, wav_path, lane_channel in zip(midi_files, wav_files, lanes):
    if not os.path.exists(midi_path) or not os.path.exists(wav_path):
        print(f"⚠️ {midi_path} 또는 {wav_path} 없음 → 건너뜀")
        continue

    print(f"\n🎼 {midi_path} + {wav_path} → 채널 {lane_channel} 병합 중...")

    mid = MidiFile(midi_path)
    ticks_per_beat = mid.ticks_per_beat
    tick_to_sec = lambda t: (t / ticks_per_beat) * (60 / bpm_default)
    audio = AudioSegment.from_file(wav_path)

    # --- MIDI 노트 추출 ---
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
    print(f"🎹 감지된 노트: {len(notes)}개")

    # --- WAV 생성 ---
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

        event_list.append((start_sec, end_sec, note, note_map[key], length_ms))

    # --- WAV 등록 추가 ---
    insert_index = len(bms_lines)
    for i, line in enumerate(bms_lines):
        if line.startswith("*---------------------- MAIN DATA FIELD"):
            insert_index = i
            break
    for (note, length), idx in sorted(note_map.items(), key=lambda x: x[1]):
        bms_lines.insert(insert_index, f"#WAV{idx:02} {os.path.basename(output_dir)}/note_{idx:02}.wav")

    # --- 레인별 마디 병합 ---
    bar_duration = (60 / bpm_default) * 4
    for start_sec, end_sec, note, wav_id, length_ms in event_list:
        measure = int(start_sec // bar_duration)
        pos = int(((start_sec % bar_duration) / bar_duration) * division)
        pos = min(pos, division - 1)
        end_measure = int(end_sec // bar_duration)
        end_pos = int(((end_sec % bar_duration) / bar_duration) * division)
        end_pos = min(end_pos, division - 1)

        # 해당 레인 초기화
        if measure not in measure_data:
            measure_data[measure] = {}
        if lane_channel not in measure_data[measure]:
            measure_data[measure][lane_channel] = ["00"] * division

        # 롱노트 처리
        if length_ms >= longnote_threshold_ms:
            # 시작
            existing = measure_data[measure][lane_channel][pos]
            measure_data[measure][lane_channel][pos] = (
                f"{wav_id:02}" if existing == "00" else existing + f"{wav_id:02}"
            )
            # 종료
            if end_measure not in measure_data:
                measure_data[end_measure] = {}
            if lane_channel not in measure_data[end_measure]:
                measure_data[end_measure][lane_channel] = ["00"] * division
            existing_end = measure_data[end_measure][lane_channel][end_pos]
            measure_data[end_measure][lane_channel][end_pos] = (
                f"{wav_id:02}" if existing_end == "00" else existing_end + f"{wav_id:02}"
            )
        else:
            # 단타
            existing = measure_data[measure][lane_channel][pos]
            measure_data[measure][lane_channel][pos] = (
                f"{wav_id:02}" if existing == "00" else existing + f"{wav_id:02}"
            )

    print(f"✅ {midi_path} 병합 완료 → 채널 {lane_channel}")

# --- MAIN DATA 다시 구성 ---
main_data = ["*---------------------- MAIN DATA FIELD"]
for measure in sorted(measure_data.keys()):
    for channel in sorted(measure_data[measure].keys()):
        data = "".join(measure_data[measure][channel])
        main_data.append(f"#{measure:03}{channel}:{data}")

# --- 저장 ---
with open(bms_path, "w", encoding="utf-8") as f:
    for line in bms_lines:
        if not line.startswith("#") or not re.match(r"#\d{3}\d{2}:", line):
            f.write(line + "\n")
    f.write("\n".join(main_data))

print("\n🎉 모든 MIDI 병합 완료 (각 레인 분리됨)")
print(f"📄 최종 BMS 파일: {bms_path}")
