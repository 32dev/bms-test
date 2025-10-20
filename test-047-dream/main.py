from mido import MidiFile
from pydub import AudioSegment
import numpy as np
import os

# === 설정 ===
midi_path = "input.mid"
output_dir = "notes"
bms_path = "output.bms"
bpm_default = 120
division = 16  # 한 마디를 16칸으로 나눔

os.makedirs(output_dir, exist_ok=True)

# --- sine wave 생성 ---
def note_to_wav(note, duration=500, filename="note.wav", volume=-10.0):
    framerate = 44100
    t = np.linspace(0, duration/1000, int(framerate * duration/1000), False)
    freq = 440.0 * 2 ** ((note - 69)/12.0)
    wave = np.sin(freq * 2 * np.pi * t)
    audio = np.int16(wave * 32767)
    segment = AudioSegment(audio.tobytes(), frame_rate=framerate, sample_width=2, channels=1)
    segment = segment + volume
    segment.export(filename, format="wav")
    return filename

# --- MIDI 읽기 ---
mid = MidiFile(midi_path)
ticks_per_beat = mid.ticks_per_beat
tick_to_sec = lambda t: (t / ticks_per_beat) * (60 / bpm_default)

# --- 노트 추출 ---
events = []
note_map = {}
wav_index = 1

for track in mid.tracks:
    current_time = 0
    for msg in track:
        current_time += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            note = msg.note
            sec = tick_to_sec(current_time)
            events.append((sec, note))
            if note not in note_map:
                filename = os.path.join(output_dir, f"note_{wav_index:02}.wav")
                note_to_wav(note, filename=filename)
                note_map[note] = wav_index
                wav_index += 1

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
for note, idx in note_map.items():
    header.append(f"#WAV{idx:02} {os.path.basename(output_dir)}/note_{idx:02}.wav")

# --- 시간 기반으로 노트 배치 ---
events.sort(key=lambda x: x[0])
total_duration = events[-1][0] if events else 0.0
bar_duration = (60 / bpm_default) * 4  # 4/4 마디 기준
num_measures = int(total_duration // bar_duration) + 1

main_data = ["*---------------------- MAIN DATA FIELD"]

for measure in range(num_measures):
    start = measure * bar_duration
    end = (measure + 1) * bar_duration
    measure_notes = [e for e in events if start <= e[0] < end]

    if not measure_notes:
        continue

    note_values = ["00"] * division
    for sec, note in measure_notes:
        pos = int(((sec - start) / bar_duration) * division)
        pos = min(pos, division - 1)
        idx = note_map[note]
        if note_values[pos] == "00":
            note_values[pos] = f"{idx:02}"
        else:
            note_values[pos] += f"{idx:02}"  # 같은 칸에 여러개

    main_data.append(f"#{measure:03}01:" + "".join(note_values))

# --- 저장 ---
with open(bms_path, "w", encoding="utf-8") as f:
    f.write("\n".join(header + main_data))

print("✅ MIDI -> WAV -> BMS 변환 완료!")
print(f"WAV 파일 위치: {output_dir}")
print(f"BMS 파일 위치: {bms_path}")
