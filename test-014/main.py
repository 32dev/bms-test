from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from mido import MidiFile, tick2second

# === 36진수 변환 함수 ===
def to_bms36(n):
    digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if n < 0 or n > 36*36-1:
        raise ValueError("BMS 36진수 범위 초과")
    return digits[n // 36] + digits[n % 36]

# === 기본 설정 ===
midi = MidiFile("song.mid")
audio = AudioSegment.from_file("song.wav")
ticks_per_beat = midi.ticks_per_beat
tempo = 500000
bpm = 120

note_segments = {}  # note -> list of [rough_start, rough_end]

# === MIDI 분석 ===
for track in midi.tracks:
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
                if note not in note_segments:
                    note_segments[note] = []
                note_segments[note].append([start_ms, None])
            else:
                if note in note_segments:
                    for seg in reversed(note_segments[note]):
                        if seg[1] is None:
                            seg[1] = start_ms
                            break

        elif msg.type == "note_off":
            note = msg.note
            end_ms = tick2second(current_tick, ticks_per_beat, tempo) * 1000
            if note in note_segments:
                for seg in reversed(note_segments[note]):
                    if seg[1] is None:
                        seg[1] = end_ms
                        break

# === 실제 소리 기반 구간 보정 ===
min_silence_len = 5
silence_thresh = -40
final_segments = []  # (note, start, end)

for note, segments in note_segments.items():
    for seg in segments:
        start, end = seg
        if start is None or end is None or end <= start:
            continue
        rough_segment = audio[int(start):int(end)]
        nonsilent = detect_nonsilent(rough_segment, min_silence_len=min_silence_len, silence_thresh=silence_thresh)
        for ns_start, ns_end in nonsilent:
            abs_start = int(start + ns_start)
            abs_end = int(start + ns_end)
            if abs_end <= abs_start:
                continue
            final_segments.append((note, abs_start, abs_end))

# === WAV ID 01부터 순차, note별 최소 1개 생성 ===
wav_counter = 1
note_to_wav = {}  # note -> wav_id
for note in note_segments:
    wav_id = to_bms36(wav_counter)
    note_to_wav[note] = wav_id
    # 첫 segment 범위로 WAV export (최소 100ms)
    first_seg = next(((s, e) for n, s, e in final_segments if n == note), None)
    if first_seg:
        start, end = first_seg
        if end - start < 100:
            end = start + 100
        segment = audio[start:end]
        segment.export(f"note_{wav_id}.wav", format="wav")
        print(f"Saved: note_{wav_id}.wav (note {note})")
    wav_counter += 1

# === BMS 데이터 준비 ===
bms_data = []
for seg_idx, (note, start, end) in enumerate(final_segments):
    wav_id = note_to_wav[note]
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
bms_lines.append("#LNTYPE 1")  # 라인 타입 필수

# === WAV 목록 작성 ===
bms_lines.append("*---------------------- WAV LIST")
for note, wav_id in note_to_wav.items():
    bms_lines.append(f"#WAV{wav_id} note_{wav_id}.wav")

# === MAIN DATA FIELD ===
bms_lines.append("*---------------------- MAIN DATA FIELD")

# 마디 단위로 lane별로 정리
bms_dict = {}  # measure -> lane -> list of (pos, wav_id)
for measure, channel, wav_id, pos in bms_data:
    if measure not in bms_dict:
        bms_dict[measure] = {}
    if channel not in bms_dict[measure]:
        bms_dict[measure][channel] = []
    bms_dict[measure][channel].append((pos, wav_id))

# 마디별로 출력 (한 마디 안에 여러 lane 기록)
for measure in sorted(bms_dict.keys()):
    measure_lanes = bms_dict[measure]
    for channel in sorted(measure_lanes.keys()):
        line_length = 192
        line = ["00"] * line_length
        for pos, wav_id in measure_lanes[channel]:
            index = int(pos / (192 / line_length))
            if 0 <= index < line_length:
                line[index] = wav_id[-2:]
        bms_lines.append(f"#{measure:03d}{channel:02d}:{''.join(line)}")

# === BMS 파일 저장 ===
with open("song.bms", "w", encoding="utf-8") as f:
    f.write("\n".join(bms_lines))

print("✅ BMS 파일 생성 완료: song.bms")
