from mido import MidiFile, tick2second
from pydub import AudioSegment
import os
import math

# === 설정 ===
MIDI_PATH = "song.mid"
WAV_PATH = "song.wav"
OUTPUT_DIR = "notes"
BMS_PATH = "song.bms"
BMA_PATH = "song.bma"

# 출력 디렉토리 생성
os.makedirs(OUTPUT_DIR, exist_ok=True)

# MIDI 및 오디오 불러오기
midi = MidiFile(MIDI_PATH)
audio = AudioSegment.from_file(WAV_PATH)

ticks_per_beat = midi.ticks_per_beat
tempo = 500000  # 기본 템포 (microseconds per beat)
bpm = 120       # BMS용 BPM 기본값

# === MIDI 분석 ===
note_events = []
for track in midi.tracks:
    absolute_time = 0
    for msg in track:
        absolute_time += msg.time
        if msg.type == 'set_tempo':
            tempo = msg.tempo
        if msg.type == 'note_on' and msg.velocity > 0:
            # tick -> 초 변환
            time_sec = tick2second(absolute_time, ticks_per_beat, tempo)
            note_events.append({
                "note": msg.note,
                "time": time_sec,
                "velocity": msg.velocity
            })
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            # 노트 종료 처리
            time_sec = tick2second(absolute_time, ticks_per_beat, tempo)
            # 기존 note_events에서 마지막 동일 노트 찾아 종료 시간 갱신
            for ne in reversed(note_events):
                if ne["note"] == msg.note and "end" not in ne:
                    ne["end"] = time_sec
                    break

# 종료시간 없는 노트 처리 (노트 길이 0.1초)
for ne in note_events:
    if "end" not in ne:
        ne["end"] = ne["time"] + 0.1

# === WAV 자르기 ===
for i, ne in enumerate(note_events):
    start_ms = int(ne["time"] * 1000)
    end_ms = int(ne["end"] * 1000)
    segment = audio[start_ms:end_ms]
    file_name = f"note_{i:03d}.wav"
    ne["wav_file"] = file_name
    segment.export(os.path.join(OUTPUT_DIR, file_name), format="wav")
    print(f"Saved note {ne['note']} → {file_name}")

# === BMS/BMA 생성 ===
with open(BMS_PATH, "w", encoding="utf-8") as bms_file, \
     open(BMA_PATH, "w", encoding="utf-8") as bma_file:

    # HEADER
    bms_file.write("*---------------------- HEADER FIELD\n")
    bms_file.write("#PLAYER 1\n#GENRE MIDI_EXPORT\n#TITLE song_export\n#ARTIST AI_GENERATED\n")
    bms_file.write(f"#BPM {bpm}\n#PLAYLEVEL 1\n#RANK 3\n#LNTYPE 1\n\n")

    bma_file.write("*---------------------- HEADER FIELD\n")
    bma_file.write("#PLAYER 1\n#GENRE MIDI_EXPORT\n#TITLE song_export\n#ARTIST AI_GENERATED\n")
    bma_file.write(f"#BPM {bpm}\n#PLAYLEVEL 1\n#RANK 3\n#LNTYPE 1\n\n")

    # WAV 매핑
    for i, ne in enumerate(note_events):
        wav_id = f"{i+1:02d}"  # 01부터 매기기
        bms_file.write(f"#WAV{wav_id} {ne['wav_file']}\n")
        bma_file.write(f"#WAV{wav_id} {ne['wav_file']}\n")
        ne["wav_id"] = wav_id

    bms_file.write("\n*---------------------- MAIN DATA FIELD\n")
    bma_file.write("\n*---------------------- MAIN DATA FIELD\n")

    # 노트 배치 (타임라인 단순 변환)
    for ne in note_events:
        measure = int(ne["time"] // 4) + 1  # 4초마다 마디 1 증가
        position = int((ne["time"] % 4) / 4 * 16)  # 16분할 기준
        code = f"{ne['wav_id']}"
        bms_file.write(f"#{measure:05d}:{position:02d}{code}\n")
        bma_file.write(f"#{measure:05d}:{position:02d}{code}\n")

print("BMS/BMA 및 WAV 추출 완료.")
