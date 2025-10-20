from mido import MidiFile
from pydub import AudioSegment
import os

# === 설정 ===
midi_path = "input.mid"
wav_path = "input.wav"
output_dir = "notes"
bms_path = "output.bms"
bpm_default = 120
division = 16  # 마디 내 분할 수
min_length_ms = 30  # 너무 짧은 노트(30ms 이하)는 무시

os.makedirs(output_dir, exist_ok=True)

# --- MIDI 읽기 ---
mid = MidiFile(midi_path)
ticks_per_beat = mid.ticks_per_beat
tick_to_sec = lambda t: (t / ticks_per_beat) * (60 / bpm_default)

# --- 원본 오디오 읽기 ---
audio = AudioSegment.from_file(wav_path)

# --- 노트 구간 계산 ---
notes = []  # [(start_sec, end_sec, note)]
for track in mid.tracks:
    current_tick = 0
    active_notes = {}
    for msg in track:
        current_tick += msg.time

        # 노트 ON
        if msg.type == "note_on" and msg.velocity > 0:
            active_notes[msg.note] = current_tick

        # 노트 OFF (note_off or velocity=0)
        elif (msg.type == "note_on" and msg.velocity == 0) or msg.type == "note_off":
            if msg.note in active_notes:
                start_tick = active_notes[msg.note]
                end_tick = current_tick
                if end_tick > start_tick:
                    notes.append((tick_to_sec(start_tick), tick_to_sec(end_tick), msg.note))
                del active_notes[msg.note]

notes.sort(key=lambda x: x[0])  # 시작시간 기준 정렬

# --- 중복 최소화 및 WAV 추출 ---
note_map = {}          # (note) -> wav_index
event_list = []        # (start_sec, note, wav_index)
wav_index = 1

for start_sec, end_sec, note in notes:
    start_ms = int(start_sec * 1000)
    end_ms = int(end_sec * 1000)
    if end_ms - start_ms < min_length_ms:
        continue

    # 동일 note 재사용 (중복 최소화)
    if note not in note_map:
        filename = os.path.join(output_dir, f"note_{wav_index:02}.wav")
        segment = audio[start_ms:end_ms]
        segment.export(filename, format="wav")
        note_map[note] = wav_index
        wav_index += 1

    # 이벤트 목록에 추가
    event_list.append((start_sec, note, note_map[note]))

print(f"🔊 {len(note_map)}개의 고유 음높이만 WAV로 생성됨 (중복 최소화 완료)")

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
bar_duration = (60 / bpm_default) * 4  # 4/4 마디 기준
total_duration = notes[-1][1] if notes else 0
num_measures = int(total_duration // bar_duration) + 1
main_data = ["*---------------------- MAIN DATA FIELD"]

for measure in range(num_measures):
    start = measure * bar_duration
    end = (measure + 1) * bar_duration
    measure_notes = [e for e in event_list if start <= e[0] < end]

    if not measure_notes:
        continue

    note_values = ["00"] * division
    for sec, note, wav_id in measure_notes:
        pos = int(((sec - start) / bar_duration) * division)
        pos = min(pos, division - 1)
        if note_values[pos] == "00":
            note_values[pos] = f"{wav_id:02}"
        else:
            note_values[pos] += f"{wav_id:02}"  # 같은 위치에 여러 개

    main_data.append(f"#{measure:03}01:" + "".join(note_values))

# --- 저장 ---
with open(bms_path, "w", encoding="utf-8") as f:
    f.write("\n".join(header + main_data))

print("✅ MIDI → WAV → BMS 변환 완료!")
print(f"📁 WAV 경로: {output_dir}")
print(f"📄 BMS 파일: {bms_path}")
