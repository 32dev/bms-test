from mido import MidiFile, tick2second
from pydub import AudioSegment
import os

# === 설정 ===
MIDI_PATH = "song.mid"
WAV_PATH = "song.wav"
OUTPUT_DIR = "notes"
BMS_PATH = "song.bms"

BPM = 120
PLAYER = 1
TITLE = "song_export"
ARTIST = "AI_GENERATED"
PLAYLEVEL = 1
RANK = 2
LNTYPE = 1

os.makedirs(OUTPUT_DIR, exist_ok=True)

# === MIDI 분석 ===
midi = MidiFile(MIDI_PATH)
ticks_per_beat = midi.ticks_per_beat
tempo = 500000

note_events = []
for track in midi.tracks:
    abs_time = 0
    for msg in track:
        abs_time += msg.time
        if msg.type == 'set_tempo':
            tempo = msg.tempo
        if msg.type == 'note_on' and msg.velocity > 0:
            start_sec = tick2second(abs_time, ticks_per_beat, tempo)
            note_events.append({"note": msg.note, "time": start_sec})

# === 중복 제거 ===
unique_notes = []
seen_notes = {}
for ne in note_events:
    key = (ne['note'], round(ne['time'], 3))  # 소수점 3자리 단위로 비교
    if key not in seen_notes:
        seen_notes[key] = True
        unique_notes.append(ne)

# === WAV 자르기 ===
audio = AudioSegment.from_file(WAV_PATH)
for i, ne in enumerate(unique_notes):
    start_ms = int(ne["time"] * 1000)
    # 끝은 다음 노트 시작 or +0.5초 최소 길이
    if i < len(unique_notes) - 1:
        end_ms = int(unique_notes[i+1]["time"] * 1000)
    else:
        end_ms = start_ms + 500
    segment = audio[start_ms:end_ms]
    file_name = f"note_{i+2:02d}.wav"  # WAV02부터 노트
    ne["wav_file"] = file_name
    segment.export(os.path.join(OUTPUT_DIR, file_name), format="wav")
    ne["wav_id"] = f"{i+2:02d}"
    print(f"Saved note {ne['note']} → {file_name}")

# === BMS 생성 ===
with open(BMS_PATH, "w", encoding="utf-8") as bms_file:
    # HEADER
    bms_file.write("*---------------------- HEADER FIELD\n")
    bms_file.write(f"#PLAYER {PLAYER}\n")
    bms_file.write("#GENRE MIDI_EXPORT\n")
    bms_file.write(f"#TITLE {TITLE}\n")
    bms_file.write(f"#ARTIST {ARTIST}\n")
    bms_file.write(f"#BPM {BPM}\n")
    bms_file.write(f"#PLAYLEVEL {PLAYLEVEL}\n")
    bms_file.write(f"#RANK {RANK}\n")
    bms_file.write(f"#LNTYPE {LNTYPE}\n\n")
    
    # WAV 매핑
    bms_file.write(f"#WAV01 {WAV_PATH}\n")  # BGM
    for ne in unique_notes:
        bms_file.write(f"#WAV{ne['wav_id']} {ne['wav_file']}\n")
    bms_file.write("\n*---------------------- MAIN DATA FIELD\n")
    
    # BGM 표시
    bms_file.write("#00001:01\n")
    
    # 노트 배치 (간단히 마디 1에 순서대로 배치)
    for ne in unique_notes:
        bms_file.write(f"#00001:{ne['wav_id']}\n")

print("BMS + 노트 WAV 생성 완료!")
