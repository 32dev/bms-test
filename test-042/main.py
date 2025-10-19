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
ARTIST = "AUTO_GENERATED"
PLAYLEVEL = 1
RANK = 3
LNTYPE = 1

MAX_LANES = 15  # UBMSC B1~B15
MEASURE_SEC = 4.0
NOTE_LENGTH_MS = 400  # WAV 클립 길이

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
unique = []
seen = set()
for ne in note_events:
    key = (ne["note"], round(ne["time"], 3))
    if key not in seen:
        seen.add(key)
        unique.append(ne)

# WAV 자르기
audio = AudioSegment.from_file(WAV_PATH)
for i, ne in enumerate(unique):
    start_ms = int(ne["time"] * 1000)
    end_ms = start_ms + NOTE_LENGTH_MS
    clip = audio[start_ms:end_ms]
    filename = f"note_{i+1:02d}.wav"
    clip.export(os.path.join(OUTPUT_DIR, filename), format="wav")
    ne["wav_id"] = f"{i+1:02d}"
    ne["wav_file"] = f"notes/{filename}"

# 시간 → 마디, 포지션 계산
for ne in unique:
    measure = int(ne["time"] // MEASURE_SEC)
    pos = int(((ne["time"] % MEASURE_SEC) / MEASURE_SEC) * 16)  # 16단위
    ne["measure"] = measure
    ne["pos"] = pos

# 88음계를 B1~B15로 그룹화
MIN_NOTE = 21
MAX_NOTE = 108
def note_to_lane(note):
    group_size = (MAX_NOTE - MIN_NOTE + 1) / MAX_LANES
    lane = int((note - MIN_NOTE) // group_size) + 1
    if lane > MAX_LANES:
        lane = MAX_LANES
    return lane

for ne in unique:
    ne["lane"] = note_to_lane(ne["note"])

# 마디별 채널 구조 생성
bms_data = {}  # {measure: {lane: {pos: wav_id}}}
for ne in unique:
    m = ne["measure"]
    lane = ne["lane"]
    pos = ne["pos"]
    wav_id = ne["wav_id"]

    bms_data.setdefault(m, {})

    # pos에서 lane 겹치면 다음 빈 lane 찾아 사용 (B1~B15 순환)
    final_lane = lane
    for i in range(MAX_LANES):
        test_lane = (lane + i - 1) % MAX_LANES + 1  # 1~15 순환
        if test_lane not in bms_data[m] or pos not in bms_data[m][test_lane]:
            final_lane = test_lane
            break

    bms_data[m].setdefault(final_lane, {})[pos] = wav_id

# === BMS 출력 ===
with open(BMS_PATH, "w", encoding="utf-8") as f:
    f.write("*---------------------- HEADER FIELD\n\n")
    f.write(f"#PLAYER {PLAYER}\n")
    f.write(f"#GENRE MIDI_EXPORT\n")
    f.write(f"#TITLE {TITLE}\n")
    f.write(f"#ARTIST {ARTIST}\n")
    f.write(f"#BPM {BPM}\n")
    f.write(f"#PLAYLEVEL {PLAYLEVEL}\n")
    f.write(f"#RANK {RANK}\n\n")
    f.write(f"#LNTYPE {LNTYPE}\n\n")

    # WAV 등록
    for ne in unique:
        f.write(f"#WAV{ne['wav_id']} {ne['wav_file']}\n")

    f.write("\n*---------------------- MAIN DATA FIELD\n\n")

    # 마디별 출력
    for measure in sorted(bms_data.keys()):
        for lane in sorted(bms_data[measure].keys()):
            channel = f"{10 + lane:02d}"  # B1~B15 = 11~25
            note_line = ["00"] * 16
            for pos, wav_id in bms_data[measure][lane].items():
                note_line[pos] = wav_id
            data = "".join(note_line)
            if not data.strip("0"):  # 완전 빈 줄은 생략
                continue
            f.write(f"#{measure:03d}{channel}:{data}\n")

print("✅ UBMSC에서 정상 열리는 BMS 생성 완료!")
