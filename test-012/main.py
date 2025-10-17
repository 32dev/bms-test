from pydub import AudioSegment
from mido import MidiFile, tick2second

# === 36진수 변환 함수 ===
def to_bms36(n):
    """00~ZZ 범위 36진수로 변환"""
    digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if n < 0 or n > 36*36-1:
        raise ValueError("BMS 36진수 범위 초과")
    return digits[n // 36] + digits[n % 36]

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
            bpm = 60000000 / tempo

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

# === 실제 존재하는 노트만 순서대로 WAV ID 매기기 ===
note_to_id = {}
valid_notes = [note for note, times in note_segments.items() if len(times) >= 2]
for idx, note in enumerate(sorted(valid_notes)):
    note_to_id[note] = idx

# === note별 오디오 자르기 + BMS 채널 데이터 준비 ===
bms_data = []

for note, times in note_segments.items():
    if note not in note_to_id:
        continue  # 끝시간 없는 노트 건너뜀

    start, end = times
    start = int(start)
    end = int(end)
    if end <= start:
        continue

    # 오디오 자르기
    segment = audio[start:end]
    wav_id = to_bms36(note_to_id[note])
    segment.export(f"note_{wav_id}.wav", format="wav")
    print(f"Saved: note_{wav_id}.wav ({end - start:.1f} ms)")

    # === BMS 좌표 계산 ===
    measure = int((start / 1000) / (60 / bpm * 4))
    pos_in_measure = ((start / 1000) % (60 / bpm * 4)) / (60 / bpm * 4)
    position = int(pos_in_measure * 192)

    lane = (note % 7) + 1
    channel = 10 + lane
    bms_data.append((measure, channel, wav_id, position))

# === BMS 헤더 작성 ===
bms_lines = []
bms_lines.append("*---------------------- HEADER FIELD")
bms_lines.append("#PLAYER 1")
bms_lines.append("#GENRE MIDI_EXPORT")
bms_lines.append("#TITLE song_export")
bms_lines.append("#ARTIST AI_GENERATED")
bms_lines.append(f"#BPM {int(bpm)}")
bms_lines.append("#PLAYLEVEL 1")
bms_lines.append("#RANK 3")

# === WAV 목록 작성 ===
bms_lines.append("*---------------------- WAV LIST")
for note in sorted(valid_notes):
    wav_id = to_bms36(note_to_id[note])
    bms_lines.append(f"#WAV{wav_id} note_{wav_id}.wav")

# === MAIN DATA FIELD ===
bms_lines.append("*---------------------- MAIN DATA FIELD")

# 마디 + 채널별 노트 정리
bms_dict = {}
for measure, channel, wav_id, pos in bms_data:
    key = (measure, channel)
    if key not in bms_dict:
        bms_dict[key] = []
    bms_dict[key].append((pos, wav_id))

# 마디 단위로 노트 기록
for (measure, channel), notes in sorted(bms_dict.items()):
    notes.sort()
    length = 192
    line = ["00"] * length
    for pos, wav_id in notes:
        index = int(pos / (192 / length))
        if 0 <= index < length:
            line[index] = wav_id[-2:]  # BMS 2자리 규격
    bms_lines.append(f"#{measure:03d}{channel:02d}:{''.join(line)}")

# === BMS 파일로 저장 ===
with open("song.bms", "w", encoding="utf-8") as f:
    f.write("\n".join(bms_lines))

print("✅ BMS 파일 생성 완료: song.bms")
