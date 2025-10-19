from mido import MidiFile, tick2second
from pydub import AudioSegment
import os

# === 설정 ===
MIDI_PATH = "song.mid"
WAV_PATH = "song.wav"  # 전체 BGM
OUTPUT_DIR = "notes"
BMS_PATH = "song.bms"

BPM = 120
PLAYER = 1
TITLE = "song_export"
ARTIST = "AI_GENERATED"
PLAYLEVEL = 1
RANK = 2
LNTYPE = 1  # 롱노트 타입 1

MEASURE_SEC = 4.0  # 1마디 기준 초
NOTE_DIV = 192     # 1마디를 192분할

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
    key = (ne['note'], round(ne['time'], 3))
    if key not in seen_notes:
        seen_notes[key] = True
        unique_notes.append(ne)

# === WAV 자르기 ===
audio = AudioSegment.from_file(WAV_PATH)
for i, ne in enumerate(unique_notes):
    start_ms = int(ne["time"] * 1000)
    if i < len(unique_notes) - 1:
        end_ms = int(unique_notes[i+1]["time"] * 1000)
    else:
        end_ms = start_ms + 500
    segment = audio[start_ms:end_ms]
    file_name = f"note_{i+2:02d}.wav"  # WAV02부터 노트
    ne["wav_file"] = file_name
    ne["wav_id"] = f"{i+2:02d}"
    segment.export(os.path.join(OUTPUT_DIR, file_name), format="wav")
    
    # 마디, 포지션 계산
    measure = int(ne["time"] // MEASURE_SEC)
    position_ratio = (ne["time"] % MEASURE_SEC) / MEASURE_SEC
    pos_index = int(position_ratio * NOTE_DIV)
    pos_index = min(pos_index, NOTE_DIV - 1)  # 오버플로 방지
    ne["measure"] = measure
    ne["position"] = pos_index

# === 노트별 실제 사용하는 레인 지정 (예시: 빨간색 레인) ===
# 노트 번호 → BMS 레인 (B1~B15)
lane_map = {
    60: 1,   # C4 → B1
    62: 2,   # D4 → B2
    64: 3,   # E4 → B3
    65: 4,   # F4 → B4
    67: 5,   # G4 → B5
    # 필요에 따라 계속 추가
}

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
    
    # B0 채널 BGM 배치 (한 마디마다 반복)
    max_measure = max(ne["measure"] for ne in unique_notes)
    for m in range(max_measure + 1):
        bms_file.write(f"#{m:03d}B0:01{'00'*(NOTE_DIV-1)}\n")
    
    # 노트 배치 (실제 지정 레인)
    for ne in unique_notes:
        note_num = ne["note"]
        if note_num not in lane_map:
            continue  # 지정 레인에 없는 노트는 건너뜀
        measure = ne["measure"]
        channel = f"B{lane_map[note_num]}"  # 지정 레인 사용
        note_line = ['00'] * NOTE_DIV
        note_line[ne["position"]] = ne['wav_id']
        note_str = ''.join(note_line)
        bms_file.write(f"#{measure:03d}{channel}:{note_str}\n")

print("✅ 실제 사용하는 레인 적용 BMS + 노트 WAV 생성 완료!")
