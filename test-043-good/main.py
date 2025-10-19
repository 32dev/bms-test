from mido import MidiFile, MidiTrack, Message
from pydub import AudioSegment
import numpy as np
import os

# === 설정 ===
midi_path = "example.mid"
output_dir = "notes"
bms_path = "example.bms"
bpm = 120

os.makedirs(output_dir, exist_ok=True)

# === 단순 sine wave로 WAV 생성 ===
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

# === MIDI 읽기 ===
mid = MidiFile(midi_path)

# 노트별 WAV 생성 및 BMS WAV 매핑
note_map = {}
wav_index = 1

for track in mid.tracks:
    for msg in track:
        if msg.type == 'note_on' and msg.velocity > 0:
            note = msg.note
            if note not in note_map:
                filename = os.path.join(output_dir, f"note_{wav_index:02}.wav")
                note_to_wav(note, filename=filename)
                note_map[note] = wav_index
                wav_index += 1

# === BMS 헤더 작성 ===
header = [
    "*---------------------- HEADER FIELD",
    "#PLAYER 1",
    "#GENRE MIDI_EXPORT",
    "#TITLE ExampleSong",
    "#ARTIST AI",
    f"#BPM {bpm}",
    "#PLAYLEVEL 1",
    "#RANK 2",
    "#LNTYPE 1"
]

# WAV 매핑 추가
for note, idx in note_map.items():
    header.append(f"#WAV{idx:02} {os.path.basename(output_dir)}/note_{idx:02}.wav")

# === BMS 메인 데이터 작성 (간단 1마디) ===
# 마디를 16분할로 나눠서 노트 배치
main_data = ["*---------------------- MAIN DATA FIELD"]
main_line = "#00001:"
note_values = ["00"] * 16

tick_per_16 = 16 // len(note_map) if len(note_map) > 0 else 1
i = 0
for note, idx in note_map.items():
    note_values[i] = f"{idx:02}"
    i += tick_per_16

main_line += "".join(note_values)
main_data.append(main_line)

# === BMS 파일 저장 ===
with open(bms_path, "w", encoding="utf-8") as f:
    f.write("\n".join(header + main_data))

print("✅ WAV 파일과 BMS 파일 생성 완료")
