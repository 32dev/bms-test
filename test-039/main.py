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

MEASURE_SEC = 4.0
NOTE_DIV = 192
MAX_LANES = 15  # UBMSC B1~B15

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

# 중복 제거
unique_notes = []
seen_notes = {}
for ne in note_events:
    key = (ne['note'], round(ne['time'], 3))
    if key not in seen_notes:
        seen_notes[key] = True
        unique_notes.append(ne)

# WAV 자르기
audio = AudioSegment.from_file(WAV_PATH)
for i, ne in enumerate(unique_notes):
    start_ms = int(ne["time"] * 1000)
    if i < len(unique_notes) - 1 and unique_notes[i+1]["time"] is not None:
        end_ms = int(unique_notes[i+1]["time"] * 1000)
    else:
        end_ms = start_ms + 500
    segment = audio[start_ms:end_ms]
    file_name = f"note_{i+2:02d}.wav"
    ne["wav_file"] = file_name
    ne["wav_id"] = f"{i+2:02d}"
    segment.export(os.path.join(OUTPUT_DIR, file_name), format="wav")
    
    measure = int(ne["time"] // MEASURE_SEC)
    position_ratio = (ne["time"] % MEASURE_SEC) / MEASURE_SEC
    pos_index = min(int(position_ratio * NOTE_DIV), NOTE_DIV - 1)
    ne["measure"] = measure
    ne["position"] = pos_index

# 자동 레인 배정
all_notes = sorted({ne["note"] for ne in unique_notes})
lane_map = {note: (i % MAX_LANES) + 1 for i, note in enumerate(all_notes)}

# BMS 데이터 구조
bms_data = {}  # bms_data[measure][pos_index] = list of (lane, wav_id)
for ne in unique_notes:
    measure = ne["measure"]
    pos = ne["position"]
    lane = lane_map[ne["note"]]
    wav_id = ne["wav_id"]

    bms_data.setdefault(measure, {})
    bms_data[measure].setdefault(pos, [])
    
    # 동시 노트가 15개를 초과하지 않도록 제한
    if len(bms_data[measure][pos]) < MAX_LANES:
        bms_data[measure][pos].append((lane, wav_id))
    # 초과 노트는 무시하거나 나중에 다른 포지션으로 이동 가능 (현재는 무시)

# BMS 파일 생성
with open(BMS_PATH, "w", encoding="utf-8") as f:
    # HEADER
    f.write("*---------------------- HEADER FIELD\n")
    f.write(f"#PLAYER {PLAYER}\n")
    f.write("#GENRE MIDI_EXPORT\n")
    f.write(f"#TITLE {TITLE}\n")
    f.write(f"#ARTIST {ARTIST}\n")
    f.write(f"#BPM {BPM}\n")
    f.write(f"#PLAYLEVEL {PLAYLEVEL}\n")
    f.write(f"#RANK {RANK}\n")
    f.write(f"#LNTYPE {LNTYPE}\n\n")

    # WAV 매핑
    for ne in unique_notes:
        f.write(f"#WAV{ne['wav_id']} {ne['wav_file']}\n")

    f.write("\n*---------------------- MAIN DATA FIELD\n")

    # 마디별, 포지션별 BMS 출력
    for measure in sorted(bms_data.keys()):
        for pos in sorted(bms_data[measure].keys()):
            line_entries = ['00'] * NOTE_DIV
            for lane, wav_id in bms_data[measure][pos]:
                # NOTE_DIV 길이 안에서 포지션만 바꿔주기
                line_entries[pos] = wav_id
            # 각 채널 라인으로 출력 (B1~B15)
            for lane_id in range(1, MAX_LANES + 1):
                channel = f"{lane_id:02d}"
                lane_line = ['00'] * NOTE_DIV
                for lane, wav_id in bms_data[measure][pos]:
                    if lane == lane_id:
                        lane_line[pos] = wav_id
                f.write(f"#{measure:03d}{channel}:{''.join(lane_line)}\n")

print("✅ UBMSC 호환 B1~B15, 동시 15개 제한 BMS 생성 완료!")
