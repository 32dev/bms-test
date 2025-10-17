from pydub import AudioSegment
from mido import MidiFile, tick2second
import math

# === 기본 설정 ===
midi = MidiFile("song.mid")
audio = AudioSegment.from_file("song.wav")

ticks_per_beat = midi.ticks_per_beat
tempo = 500000  # 기본 템포 (120BPM)
bpm = 120       # BMS용 BPM 기본값
note_segments = {}

# === MIDI 분석 ===
for i, track in enumerate(midi.tracks):
    current_tick = 0
    for msg in track:
        current_tick += msg.time

        if msg.type == "set_tempo":
            tempo = msg.tempo
            bpm = 60000000 / tempo  # μs per beat → BPM

        elif msg.type == "note_on":
            note = msg.note
            start_ms = tick2second(current_tick, ticks_per_beat, tempo) * 1000

            if msg.velocity > 0:
                if note in note_segments and len(note_segments[note]) == 1:
                    note_segments[note].append(start_ms)
                note_segments[note] = [start_ms]
            else:
                if note in note_segments and len(note_segments[note]) == 1:
                    end_ms = start_ms
                    note_segments[note].append(end_ms)

        elif msg.type == "note_off":
            note = msg.note
            end_ms = tick2second(current_tick, ticks_per_beat, tempo) * 1000
            if note in note_segments and len(note_segments[note]) == 1:
                note_segments[note].append(end_ms)

# === note별 오디오 자르기 + BMS 채널 데이터 준비 ===
bms_data = []   # [(measure, channel, wav_id, position)]

for i, (note, times) in enumerate(sorted(note_segments.items())):
    if len(times) < 2:
        print(f"Skipping note {note} (no end time)")
        continue

    start, end = times
    start = int(start)
    end = int(end)
    if end <= start:
        continue

    # 오디오 자르기
    segment = audio[start:end]
    wav_name = f"{note:03d}"
    segment.export(f"note_{wav_name}.wav", format="wav")
    print(f"Saved: note_{wav_name}.wav ({end - start:.1f} ms)")

    # === BMS 좌표 계산 ===
    # 1마디 = 4비트 기준
    measure = int((start / 1000) / (60 / bpm * 4))
    pos_in_measure = ((start / 1000) % (60 / bpm * 4)) / (60 / bpm * 4)
    position = int(pos_in_measure * 192)  # 192 divisions per measure

    # 간단하게 1~7번키에 분배
    lane = (note % 7) + 1
    channel = 10 + lane   # 11~17: 7키
    bms_data.append((measure, channel, wav_name, position))

# === BMS 헤더 작성 ===
bms_lines = []
bms_lines.append("*---------------------- HEADER FIELD")
bms_lines.append(f"#PLAYER 1")
bms_lines.append(f"#GENRE MIDI_EXPORT")
bms_lines.append(f"#TITLE song_export")
bms_lines.append(f"#ARTIST AI_GENERATED")
bms_lines.append(f"#BPM {int(bpm)}")
bms_lines.append(f"#PLAYLEVEL 1")
bms_lines.append(f"#RANK 3")
bms_lines.append("*---------------------- WAV LIST")

# === WAV 목록 ===
for i, (note, _) in enumerate(sorted(note_segments.items())):
    if len(note_segments[note]) >= 2:
        wav_id = f"{note:03d}"
        bms_lines.append(f"#WAV{wav_id} note_{wav_id}.wav")

bms_lines.append("*---------------------- MAIN DATA FIELD")

# === 노트 이벤트 ===
bms_dict = {}
for measure, channel, wav_id, pos in bms_data:
    key = (measure, channel)
    if key not in bms_dict:
        bms_dict[key] = []
    bms_dict[key].append((pos, wav_id))

# === 마디 단위로 정렬하여 작성 ===
for (measure, channel), notes in sorted(bms_dict.items()):
    notes.sort()
    max_pos = max(pos for pos, _ in notes) if notes else 0
    length = 192  # 기본분할
    line = ["00"] * length
    for pos, wav_id in notes:
        index = int(pos / (192 / length))
        if 0 <= index < length:
            line[index] = wav_id[-2:]  # 두 자리만 사용 (BMS 규격)
    bms_lines.append(f"#{measure:03d}{channel:02d}:{''.join(line)}")

# === 파일로 저장 ===
with open("song.bms", "w", encoding="utf-8") as f:
    f.write("\n".join(bms_lines))

print("✅ BMS 파일 생성 완료: song.bms")
