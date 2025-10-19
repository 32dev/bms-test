from pydub import AudioSegment
from mido import MidiFile, tick2second
import os, math

# === 기본 설정 ===
midi = MidiFile("song.mid")
audio = AudioSegment.from_file("song.wav")

ticks_per_beat = midi.ticks_per_beat
tempo = 500000  # 기본 템포 (120BPM)
bpm = 120
note_segments = {}

# === 출력 폴더 ===
os.makedirs("notes", exist_ok=True)

# === MIDI 분석 ===
for track in midi.tracks:
    current_time = 0
    for msg in track:
        current_time += msg.time
        if msg.type == "set_tempo":
            tempo = msg.tempo
        elif msg.type == "note_on" and msg.velocity > 0:
            start_time = tick2second(current_time, ticks_per_beat, tempo)
            note_segments.setdefault(msg.note, []).append({"start": start_time})
        elif msg.type in ["note_off", "note_on"] and msg.velocity == 0:
            end_time = tick2second(current_time, ticks_per_beat, tempo)
            if msg.note in note_segments and note_segments[msg.note]:
                if "end" not in note_segments[msg.note][-1]:
                    note_segments[msg.note][-1]["end"] = end_time

# === 사운드 자르기 ===
for i, (note, segs) in enumerate(note_segments.items(), start=1):
    for j, seg in enumerate(segs, start=1):
        if "end" not in seg:
            continue
        start_ms = seg["start"] * 1000
        end_ms = seg["end"] * 1000
        if end_ms > start_ms:
            clip = audio[start_ms:end_ms]
            filename = f"notes/note_{i:02}_{j:03}.wav"
            clip.export(filename, format="wav")
            seg["file"] = filename

# === 해상도 세밀 조정 ===
resolution = 20000  # 박자 세분화

def sec_to_bms_pos(sec):
    beat = (sec * bpm) / 60
    return int(beat * resolution)

# === 전체 노트 리스트 정렬 ===
all_notes = []
for note, segs in note_segments.items():
    for seg in segs:
        if "end" in seg and "file" in seg:
            all_notes.append({
                "note": note,
                "start": sec_to_bms_pos(seg["start"]),
                "file": seg["file"]
            })

all_notes.sort(key=lambda n: n["start"])

# === BMS 헤더 ===
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

# === WAV 매핑 ===
unique_files = []
for n in all_notes:
    if n["file"] not in unique_files:
        unique_files.append(n["file"])

for i, fpath in enumerate(unique_files, start=1):
    wid = f"{i:02}"
    name = os.path.basename(fpath)
    bms.append(f"#WAV{wid} {name}")

# === 노트 배치 ===
bms.append("\n*---------------------- MAIN DATA FIELD")
measure_notes = {}

for n in all_notes:
    measure = n["start"] // (resolution * 4)
    position = (n["start"] % (resolution * 4)) / (resolution * 4)
    key = f"{measure:03}"
    wav_index = unique_files.index(n["file"]) + 1
    lane_id = (n["note"] % 4) + 1  # 4키 기준

    measure_notes.setdefault((key, lane_id), []).append((position, f"{wav_index:02}"))

for (measure, lane), notes in sorted(measure_notes.items()):
    notes.sort(key=lambda x: x[0])
    total = len(notes)
    seq = "".join([wid for _, wid in notes])
    bms.append(f"#{measure}{10+lane}:{seq}")

# === 저장 ===
with open("output.bms", "w", encoding="utf-8") as f:
    f.write("\n".join(bms))

print("✅ 변환 완료: output.bms 생성")
print("🎧 잘린 노트 WAV: ./notes 폴더에 저장됨")
