from mido import MidiFile, tick2second
import os

# === 설정 ===
MIDI_PATH = "song.mid"
WAV_PATH = "song.wav"
BMS_PATH = "song.bms"

BPM = 120
PLAYER = 1
TITLE = "song_export"
ARTIST = "AI_GENERATED"
PLAYLEVEL = 1
RANK = 2
LNTYPE = 1  # 롱노트 타입 1

# MIDI 파일 열기
midi = MidiFile(MIDI_PATH)
ticks_per_beat = midi.ticks_per_beat
tempo = 500000  # 기본 템포 (microseconds per beat)

# 마지막 노트 시간 계산
last_time_sec = 0
for track in midi.tracks:
    abs_time = 0
    for msg in track:
        abs_time += msg.time
        if msg.type == 'set_tempo':
            tempo = msg.tempo
        if msg.type in ['note_on', 'note_off']:
            time_sec = tick2second(abs_time, ticks_per_beat, tempo)
            if time_sec > last_time_sec:
                last_time_sec = time_sec

# 4분의 마디 기준으로 마디 수 계산 (1마디=4초 기준)
# Bemusescript에서는 단순히 마지막 마디 번호를 참조
measure_length_sec = 4  # 기본 4초 = 1마디
last_measure = int(last_time_sec // measure_length_sec) + 1

# BMS 파일 생성
with open(BMS_PATH, "w", encoding="utf-8") as bms_file:
    # ---------------- HEADER FIELD ----------------
    bms_file.write("*---------------------- HEADER FIELD\n")
    bms_file.write(f"#PLAYER {PLAYER}\n")
    bms_file.write("#GENRE BGM_ONLY\n")
    bms_file.write(f"#TITLE {TITLE}\n")
    bms_file.write(f"#ARTIST {ARTIST}\n")
    bms_file.write(f"#BPM {BPM}\n")
    bms_file.write(f"#PLAYLEVEL {PLAYLEVEL}\n")
    bms_file.write(f"#RANK {RANK}\n")
    bms_file.write(f"#LNTYPE {LNTYPE}\n\n")
    
    # WAV 매핑 (BGM)
    bms_file.write(f"#WAV01 {WAV_PATH}\n\n")
    
    # ---------------- MAIN DATA FIELD ----------------
    bms_file.write("*---------------------- MAIN DATA FIELD\n")
    # 마디 1부터 마지막 마디까지 BGM 시작 표시
    for measure in range(1, last_measure + 1):
        bms_file.write(f"#{measure:05d}:01\n")

print(f"Bemusescript용 BMS 파일 생성 완료! (총 마디: {last_measure})")
