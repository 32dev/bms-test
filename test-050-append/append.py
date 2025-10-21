from mido import MidiFile
from pydub import AudioSegment
import os
import re

# === 설정 ===
midi_path = "input2.mid"
wav_path = "input2.wav"
output_dir = "notes"
bms_path = "output.bms"
bpm_default = 120
division = 16
min_length_ms = 30

os.makedirs(output_dir, exist_ok=True)

# --- 기존 BMS 읽기 ---
if not os.path.exists(bms_path):
    print("⚠️ 기존 output.bms 파일이 없습니다. 먼저 main.py로 생성하세요.")
    exit()

with open(bms_path, "r", encoding="utf-8") as f:
    bms_lines = f.read().splitlines()

# 기존 WAV 인덱스 최대값 찾기 (#WAVxx)
wav_ids = [int(m.group(1)) for line in bms_lines if (m := re.match(r"#WAV(\d{2})", line))]
next_wav_index = (max(wav_ids) + 1) if wav_ids else 1
print(f"🎧 기존 BMS에서 다음 WAV 인덱스 시작: {next_wav_index:02}")

# 기존 마디 데이터 추출
measure_data = {}
for line in bms_lines:
    m = re.match(r"#(\d{3})01:(.*)", line)
    if m:
        measure = int(m.group(1))
        data = m.group(2)
        measure_data[measure] = list(re.findall("..", data))  # 2자리씩 분리

# --- 새로운 MIDI 로드 ---
mid = MidiFile(midi_path)
ticks_per_beat = mid.ticks_per_beat
tick_to_sec = lambda t: (t / ticks_per_beat) * (60 / bpm_default)
audio = AudioSegment.from_file(wav_path)

# --- 노트 추출 ---
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
print(f"🎹 MIDI에서 {len(notes)}개의 노트를 감지했습니다.")

# --- 새로운 WAV 생성 및 이벤트 구성 ---
note_map = {}
event_list = []
wav_index = next_wav_index

for start_sec, end_sec, note in notes:
    start_ms = int(start_sec * 1000)
    end_ms = int(end_sec * 1000)
    if end_ms - start_ms < min_length_ms:
        continue

    if note not in note_map:
        filename = os.path.join(output_dir, f"note_{wav_index:02}.wav")
        segment = audio[start_ms:end_ms]
        segment.export(filename, format="wav")
        note_map[note] = wav_index
        wav_index += 1

    event_list.append((start_sec, note, note_map[note]))

# --- BMS에 새 WAV 등록 추가 ---
insert_index = len(bms_lines)
for i, line in enumerate(bms_lines):
    if line.startswith("*---------------------- MAIN DATA FIELD"):
        insert_index = i
        break

for note, idx in sorted(note_map.items(), key=lambda x: x[1]):
    bms_lines.insert(insert_index, f"#WAV{idx:02} {os.path.basename(output_dir)}/note_{idx:02}.wav")

# --- 노트를 기존 마디에 병합 ---
bar_duration = (60 / bpm_default) * 4
for start_sec, note, wav_id in event_list:
    measure = int(start_sec // bar_duration)
    pos = int(((start_sec % bar_duration) / bar_duration) * division)
    pos = min(pos, division - 1)
    if measure not in measure_data:
        measure_data[measure] = ["00"] * division
    existing = measure_data[measure][pos]
    if existing == "00":
        measure_data[measure][pos] = f"{wav_id:02}"
    else:
        measure_data[measure][pos] += f"{wav_id:02}"

# --- 새로운 MAIN DATA 다시 구성 ---
main_data = ["*---------------------- MAIN DATA FIELD"]
for measure in sorted(measure_data.keys()):
    data = "".join(measure_data[measure])
    main_data.append(f"#{measure:03}01:{data}")

# --- 저장 ---
with open(bms_path, "w", encoding="utf-8") as f:
    for line in bms_lines:
        if not line.startswith("#") or not re.match(r"#\d{3}01:", line):
            f.write(line + "\n")
    f.write("\n".join(main_data))

print("✅ 새로운 MIDI가 기존 타임라인(0초 기준)에 병합되었습니다.")
print(f"📄 수정된 BMS 파일: {bms_path}")
