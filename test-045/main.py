from mido import MidiFile
from pydub import AudioSegment
import numpy as np
import os

# === 설정 ===
midi_path = "input.mid"       # 변환할 MIDI 파일
output_dir = "notes"          # WAV 저장 폴더
bms_path = "output.bms"       # 생성될 BMS 파일
bpm_default = 120             # 기본 BPM
division = 16                 # 마디 내 분할 수 (예: 16분할)

os.makedirs(output_dir, exist_ok=True)

# --- 단순 sine wave로 WAV 생성 함수 ---
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

# --- 노트 추출 및 WAV 생성 ---
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

# --- BMS 헤더 작성 ---
header = [
    "*---------------------- HEADER FIELD",
    "#PLAYER 1",
    "#GENRE MIDI_EXPORT",
    "#TITLE " + os.path.basename(midi_path),
    "#ARTIST AI",
    f"#BPM {bpm_default}",
    "#PLAYLEVEL 1",
    "#RANK 2",
    "#LNTYPE 1"
]

# WAV 매핑 추가
for note, idx in note_map.items():
    header.append(f"#WAV{idx:02} {os.path.basename(output_dir)}/note_{idx:02}.wav")

# --- BMS 메인 데이터 작성 (단일 마디, 균등 배치) ---
main_data = ["*---------------------- MAIN DATA FIELD"]
note_values = ["00"] * division
note_list = sorted(note_map.items())
N = len(note_list)

if N == 1:
    note_values[0] = f"{note_list[0][1]:02}"  # 노트가 1개면 첫 칸
else:
    for i, (note, idx) in enumerate(note_list):
        pos = round(i * (division - 1) / (N - 1))  # 0 ~ division-1 균등 배치
        if note_values[pos] == "00":
            note_values[pos] = f"{idx:02}"
        else:
            # 동시 노트 처리: [01 02] 형태
            existing = note_values[pos].replace("[", "").replace("]", "")
            note_values[pos] = f"[{existing} {idx:02}]"

main_data.append("#00001:" + "".join(note_values))

# --- BMS 파일 저장 ---
with open(bms_path, "w", encoding="utf-8") as f:
    f.write("\n".join(header + main_data))

print("✅ MIDI -> WAV -> BMS 변환 완료!")
print(f"WAV 파일 위치: {output_dir}")
print(f"BMS 파일 위치: {bms_path}")
