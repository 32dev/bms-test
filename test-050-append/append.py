from mido import MidiFile
from pydub import AudioSegment
import os
import re

# === 설정 ===
midi_path = "part2.mid"
wav_path = "part2.wav"
output_dir = "notes"
bms_path = "output.bms"
bpm_default = 120
division = 16
max_simultaneous_notes = 15
min_length_ms = 1

os.makedirs(output_dir, exist_ok=True)

# --- 기존 BMS 읽기 ---
existing_main_data = []
existing_note_map = {}  # note -> wav_index

if os.path.exists(bms_path):
    with open(bms_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    header_section = True
    for line in lines:
        line = line.strip()
        if line.startswith("*---------------------- MAIN DATA FIELD"):
            header_section = False
            continue
        if header_section and line.startswith("#WAV"):
            # 기존 WAV 매핑 읽기
            m = re.match(r"#WAV(\d{2})\s+.*note_(\d{2})\.wav", line)
            if m:
                idx = int(m.group(1))
                note_num = int(m.group(2))  # 기존 WAV 파일 번호로 음 재사용
                existing_note_map[note_num] = idx
        elif not header_section:
            existing_main_data.append(line)

# --- MIDI 읽기 ---
mid = MidiFile(midi_path)
ticks_per_beat = mid.ticks_per_beat
tick_to_sec = lambda t: (t / ticks_per_beat) * (60 / bpm_default)

# --- WAV 읽기 ---
audio = AudioSegment.from_file(wav_path)

# --- 노트 구간 계산 ---
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

# --- WAV 추출 및 note_map 생성 (기존 WAV 재사용) ---
note_map = existing_note_map.copy()
event_list = []
wav_index = max(note_map.values(), default=0) + 1

for start_sec, end_sec, note in notes:
    start_ms = int(start_sec * 1000)
    end_ms = int(end_sec * 1000)
    if end_ms - start_ms < min_length_ms:
        end_ms = start_ms + min_length_ms

    if note not in note_map:
        filename = os.path.join(output_dir, f"note_{wav_index:02}.wav")
        segment = audio[start_ms:end_ms]
        segment.export(filename, format="wav")
        note_map[note] = wav_index
        wav_index += 1

    event_list.append((start_sec, note, note_map[note]))

print(f"🔊 총 {len(note_map)}개의 WAV 파일 매핑 완료")

# --- BMS 헤더 작성 ---
header = [
    "*---------------------- HEADER FIELD",
    "#PLAYER 1",
    "#GENRE MIDI_EXPORT",
    f"#TITLE {os.path.basename(midi_path)}",
    "#ARTIST AI",
    f"#BPM {bpm_default}",
    "#PLAYLEVEL 1",
    "#RANK 2",
    "#LNTYPE 1"
]

# WAV 매핑 출력 (기존 + 새로 생성)
for note, idx in sorted(note_map.items(), key=lambda x: x[1]):
    header.append(f"#WAV{idx:02} {os.path.basename(output_dir)}/note_{idx:02}.wav")

# --- BMS 메인데이터 작성 ---
bar_duration = (60 / bpm_default) * 4
total_duration = notes[-1][1] if notes else 0
num_measures = int(total_duration // bar_duration) + 1
main_data = ["*---------------------- MAIN DATA FIELD"]

for measure in range(num_measures):
    start = measure * bar_duration
    end = (measure + 1) * bar_duration
    measure_notes = [e for e in event_list if start <= e[0] < end]

    if not measure_notes:
        continue

    # 타임 슬롯별 WAV 그룹화
    time_slots = {}
    for sec, note, wav_id in measure_notes:
        pos = int(((sec - start) / bar_duration) * division)
        pos = min(pos, division - 1)
        time_slots.setdefault(pos, []).append(wav_id)

    # 최대 15 레인(B1~B15) 안에서 동시노트 배치
    rows = [["00"] * division for _ in range(max_simultaneous_notes)]
    for pos, wavs in time_slots.items():
        for i, wav_id in enumerate(wavs[:max_simultaneous_notes]):
            rows[i][pos] = f"{wav_id:02}"

    for row in rows:
        if any(v != "00" for v in row):
            main_data.append(f"#{measure:03}01:" + "".join(row))

# --- 기존 MAIN DATA와 합치기 ---
if existing_main_data:
    main_data = existing_main_data + main_data

# --- BMS 저장 ---
with open(bms_path, "w", encoding="utf-8") as f:
    f.write("\n".join(header + main_data))

print("✅ MIDI → WAV → BMS 변환 완료 (기존 WAV 재사용 + B1~B15 동시노트 처리)")
print(f"📁 WAV 경로: {output_dir}")
print(f"📄 BMS 파일: {bms_path}")
