from pydub import AudioSegment
from mido import MidiFile, tick2second
import math
import os

# === 기본 설정 ===
midi_file = "song.mid"
audio_file = "song.wav"
output_bms = "song.bms"

midi = MidiFile(midi_file)
audio = AudioSegment.from_file(audio_file)

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

    # 오디오 자르기 → OGG로 저장
    segment = audio[start:end]
    wav_id = f"{i:02d}"  # 2자리 ID (UBMSC 호환)
    segment.export(f"note_{wav_id}.ogg", format="ogg")
    print(f"Saved: note_{wav_id}.ogg ({end - start:.1f} ms)")

    # === BMS 좌표 계산 ===
    measure = int((start / 1000) / (60 / bpm * 4))
    pos_in_measure = ((start / 1000) % (60 / bpm * 4)) / (60 / bpm * 4)
    position = int(pos_in_measure * 192)  # 192 divisions per measure

    # 7키 채널 (UBMSC 호환: 01~07)
    lane = (note % 7) + 1
    channel = lane  # UBMSC용 1~7채널
    bms_data.append((measure, channel, wav_id, position))

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

# === WAV 목록 작성 (OGG) ===
for i in range(len(note_segments)):
    wav_id = f"{i:02d}"
    if os.path.exists(f"note_{wav_id}.ogg"):
        bms_lines.append(f"#WAV{wav_id} note_{wav_id}.ogg")

bms_lines.append("*---------------------- MAIN DATA FIELD")

# === 노트 이벤트 정리 ===
bms_dict = {}
for measure, channel, wav_id, pos in bms_data:
    key = (measure, channel)
    if key not in bms_dict:
        bms_dict[key] = []
    bms_dict[key].append((pos, wav_id))

# === 마디 단위로 정렬하여 작성 ===
for (measure, channel), notes in sorted(bms_dict.items()):
    notes.sort()
    length = 192  # 기본분할
    line = ["00"] * length
    for pos, wav_id in notes:
        index = int(pos / (192 / length))
        if 0 <= index < length:
            line[index] = wav_id  # 2자리 ID 그대로 사용
    bms_lines.append(f"#{measure:03d}{channel:02d}:{''.join(line)}")

# === BMS 파일 저장 ===
with open(output_bms, "w", encoding="utf-8") as f:
    f.write("\n".join(bms_lines))

print(f"✅ BMS 파일 생성 완료: {output_bms}")
