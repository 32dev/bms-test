from mido import MidiFile
from pydub import AudioSegment
import os

# === 설정 ===
midi_path = "input.mid"
wav_path = "input.wav"
output_dir = "notes"
bms_path = "output.bms"
bpm_default = 120
division = 16        # 마디 내 분할 수
max_simultaneous_notes = 15  # 한 타임에 최대 노트 수
min_length_ms = 1    # 너무 짧은 노트는 무시하지 않음

os.makedirs(output_dir, exist_ok=True)

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

# --- WAV 추출 및 note_map 생성 ---
note_map = {}
event_list = []
wav_index = 1

for start_sec, end_sec, note in notes:
    start_ms = int(start_sec * 1000)
    end_ms = int(end_sec * 1000)
    if end_ms - start_ms < min_length_ms:
        end_ms = start_ms + min_length_ms  # 최소 길이 적용

    if note not in note_map:
        filename = os.path.join(output_dir, f"note_{wav_index:02}.wav")
        segment = audio[start_ms:end_ms]
        segment.export(filename, format="wav")
        note_map[note] = wav_index
        wav_index += 1

    event_list.append((start_sec, note, note_map[note]))

print(f"🔊 {len(note_map)}개의 고유 WAV 생성 완료")

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

for note, idx in sorted(note_map.items(), key=lambda x: x[1]):
    header.append(f"#WAV{idx:02} {os.path.basename(output_dir)}/note_{idx:02}.wav")

# --- BMS 메인데이터 작성 ---
bar_duration = (60 / bpm_default) * 4  # 4/4 기준
total_duration = notes[-1][1] if notes else 0
num_measures = int(total_duration // bar_duration) + 1
main_data = ["*---------------------- MAIN DATA FIELD"]

for measure in range(num_measures):
    start = measure * bar_duration
    end = (measure + 1) * bar_duration
    measure_notes = [e for e in event_list if start <= e[0] < end]

    if not measure_notes:
        continue

    # 타임 슬롯별로 WAV 그룹화
    time_slots = {}
    for sec, note, wav_id in measure_notes:
        pos = int(((sec - start) / bar_duration) * division)
        pos = min(pos, division - 1)
        time_slots.setdefault(pos, []).append(wav_id)

    # 행 생성
    rows = [["00"] * division for _ in range(max_simultaneous_notes)]

    for pos in range(division):
        if pos not in time_slots:
            continue
        wavs = time_slots[pos]
        for i, wav_id in enumerate(wavs):
            if i >= max_simultaneous_notes:
                # 동시에 15개 초과 노트는 새로운 행 생성
                rows.append(["00"] * division)
            rows[i][pos] = f"{wav_id:02}"

    for row in rows:
        main_data.append(f"#{measure:03}01:" + "".join(row))

# --- BMS 저장 ---
with open(bms_path, "w", encoding="utf-8") as f:
    f.write("\n".join(header + main_data))

print("✅ MIDI → WAV → BMS 변환 완료!")
print(f"📁 WAV 경로: {output_dir}")
print(f"📄 BMS 파일: {bms_path}")
