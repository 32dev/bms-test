from pydub import AudioSegment
from mido import MidiFile, tick2second
import math

# === 기본 설정 ===
midi = MidiFile("song.mid")
audio = AudioSegment.from_file("song.wav")

ticks_per_beat = midi.ticks_per_beat
tempo = 500000  # 기본 템포 (120 BPM)
bpm = 120
note_segments = {}

# === MIDI 분석 ===
for track in midi.tracks:
    current_time = 0
    for msg in track:
        current_time += msg.time
        if msg.type == "set_tempo":
            tempo = msg.tempo
        elif msg.type == "note_on" and msg.velocity > 0:
            start_time = tick2second(current_time, ticks_per_beat, tempo)
            note_segments.setdefault(msg.note, []).append(
                {"start": start_time})
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            end_time = tick2second(current_time, ticks_per_beat, tempo)
            if msg.note in note_segments and note_segments[msg.note]:
                note_segments[msg.note][-1]["end"] = end_time

# === 시간 단위 해상도 조정 ===
# tick이 아닌 "beat × 10000" 단위로 세분화 → 미세 박자 인식
resolution = 10000


def sec_to_bms_pos(sec):
    beat = (sec * bpm) / 60
    return int(beat * resolution)


# === 노트 정렬 ===
all_notes = []
for note, segments in note_segments.items():
    for seg in segments:
        if "end" in seg:
            all_notes.append({
                "note": note,
                "start": sec_to_bms_pos(seg["start"]),
                "end": sec_to_bms_pos(seg["end"]),
            })

all_notes.sort(key=lambda n: n["start"])

# === BMS 헤더 출력 ===
bms = []
bms.append("*---------------------- HEADER FIELD")
bms.append("#PLAYER 1")
bms.append("#GENRE MIDI_EXPORT")
bms.append("#TITLE song_export")
bms.append("#ARTIST AI_GENERATED")
bms.append(f"#BPM {bpm}")
bms.append("#PLAYLEVEL 1")
bms.append("#RANK 3")
bms.append("#LNTYPE 1\n")

# === WAV 맵핑 ===
for i, note in enumerate(sorted(note_segments.keys())):
    wid = f"{i+1:02}"
    bms.append(f"#WAV{wid} note_{wid}.wav")

# === 노트 출력 ===
bms.append("\n*---------------------- MAIN DATA FIELD")

# 박자별 노트 배치
measure_notes = {}
for n in all_notes:
    measure = n["start"] // (resolution * 4)
    position = (n["start"] % (resolution * 4)) / (resolution * 4)
    key = f"{measure:03}"

    lane_id = (n["note"] % 4) + 1  # 단순 4키 분배
    wav_id = f"{(n['note'] % len(note_segments)) + 1:02}"
    line = measure_notes.setdefault((key, lane_id), [])
    line.append((position, wav_id))

# === 출력 구성 ===
for (measure, lane), notes in sorted(measure_notes.items()):
    notes.sort(key=lambda x: x[0])
    length = len(notes)
    data = "".join([f"{wid}" for _, wid in notes])
    bms.append(f"#{measure}{10+lane}:{data}")

# === 파일로 저장 ===
with open("output.bms", "w", encoding="utf-8") as f:
    f.write("\n".join(bms))

print("✅ 변환 완료: output.bms")
