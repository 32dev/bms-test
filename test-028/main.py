from pydub import AudioSegment
from mido import MidiFile
import os, math

# === 설정 ===
midi_path = "song.mid"
wav_path = "song.wav"
output_dir = "notes"
bms_path = "song.bms"
bma_path = "song.bma"

os.makedirs(output_dir, exist_ok=True)

# === MIDI 및 오디오 불러오기 ===
midi = MidiFile(midi_path)
audio = AudioSegment.from_file(wav_path)
ticks_per_beat = midi.ticks_per_beat

# === tempo 계산 ===
tempo = 500000  # 기본 120BPM
time_per_tick = tempo / ticks_per_beat / 1_000_000  # tick → sec
note_times = {}
current_tick = 0
current_time = 0.0

for track in midi.tracks:
    current_tick = 0
    current_time = 0.0
    tempo = 500000
    time_per_tick = tempo / ticks_per_beat / 1_000_000

    for msg in track:
        current_tick += msg.time
        current_time += msg.time * time_per_tick

        if msg.type == "set_tempo":
            tempo = msg.tempo
            time_per_tick = tempo / ticks_per_beat / 1_000_000

        elif msg.type == "note_on" and msg.velocity > 0:
            note_times.setdefault(msg.note, []).append({"start": current_time})

        elif msg.type in ["note_off", "note_on"] and msg.velocity == 0:
            if msg.note in note_times and note_times[msg.note]:
                note_times[msg.note][-1]["end"] = current_time

# === 오디오 자르기 및 WAV 추출 ===
wav_id_map = {}
wav_counter = 1

for note, events in sorted(note_times.items()):
    first_clip = None
    for i, ev in enumerate(events, start=1):
        if "end" not in ev:
            continue
        start_ms = ev["start"] * 1000
        end_ms = ev["end"] * 1000
        if end_ms - start_ms < 20:
            end_ms = start_ms + 50

        clip = audio[start_ms:end_ms]
        out_name = f"note_{wav_counter:02}.wav"
        clip.export(os.path.join(output_dir, out_name), format="wav")

        # 첫 번째 노트를 대표 wav로 지정
        if first_clip is None:
            first_clip = out_name

    wav_id_map[note] = f"{wav_counter:02}"
    print(f"Saved note {note} → {first_clip}")
    wav_counter += 1

# === BPM 계산 (기본 120)
bpm = 60000000 / tempo if tempo else 120

# === BMS 및 BMA 공통 헤더 ===
header = [
    "*---------------------- HEADER FIELD",
    "#PLAYER 1",
    "#GENRE MIDI_EXPORT",
    "#TITLE song_export",
    "#ARTIST AUTO_GENERATED",
    f"#BPM {int(bpm)}",
    "#PLAYLEVEL 1",
    "#RANK 3",
    "#LNTYPE 1",
    "*---------------------- WAV LIST"
]

# === WAV 리스트 추가 ===
for note, wav_id in wav_id_map.items():
    header.append(f"#WAV{wav_id} {output_dir}/note_{wav_id}.wav")

header.append("*---------------------- MAIN DATA FIELD")

# === BMS 데이터 생성 ===
bms_dict = {}
for note, events in note_times.items():
    for ev in events:
        if "end" not in ev:
            continue
        start_time = ev["start"]
        measure = int((start_time * bpm / 60) / 4)
        pos_in_measure = ((start_time * bpm / 60) % 4) / 4
        position = int(pos_in_measure * 192)

        lane = (note % 7) + 1
        channel = 10 + lane
        wav_id = wav_id_map[note]

        if measure not in bms_dict:
            bms_dict[measure] = {}
        if channel not in bms_dict[measure]:
            bms_dict[measure][channel] = []

        bms_dict[measure][channel].append((position, wav_id))

# === 마디별 데이터 출력 ===
bms_lines = []
for measure in sorted(bms_dict.keys()):
    for channel in sorted(bms_dict[measure].keys()):
        line = ["00"] * 192
        for pos, wav_id in bms_dict[measure][channel]:
            idx = min(int(pos / (192 / len(line))), len(line) - 1)
            line[idx] = wav_id
        bms_lines.append(f"#{measure:03d}{channel:02d}:{''.join(line)}")

# === BMS / BMA 저장 ===
with open(bms_path, "w", encoding="utf-8") as f:
    f.write("\n".join(header + bms_lines))
print(f"✅ BMS 파일 저장 완료: {bms_path}")

with open(bma_path, "w", encoding="utf-8") as f:
    f.write("\n".join(header + bms_lines))
print(f"✅ BMA 파일 저장 완료: {bma_path}")
