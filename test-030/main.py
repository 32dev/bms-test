from pydub import AudioSegment
from mido import MidiFile
import os

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

# === tempo events 수집 ===
tempo = 500000  # 기본 120BPM
tempo_events = [(0, tempo)]  # (tick, tempo)

for track in midi.tracks:
    tick_acc = 0
    for msg in track:
        tick_acc += msg.time
        if msg.type == "set_tempo":
            tempo_events.append((tick_acc, msg.tempo))
tempo_events.sort()

# === tick → seconds 변환 함수 ===
def tick_to_seconds(tick):
    total_time = 0.0
    for i in range(len(tempo_events)):
        t_tick, t_tempo = tempo_events[i]
        next_tick = tempo_events[i + 1][0] if i + 1 < len(tempo_events) else tick
        if tick <= next_tick:
            total_time += (tick - t_tick) * (t_tempo / ticks_per_beat / 1_000_000)
            break
        else:
            total_time += (next_tick - t_tick) * (t_tempo / ticks_per_beat / 1_000_000)
    return total_time

# === 모든 노트 시간 수집 (트랙 통합) ===
note_events = {}
active_notes = {}  # 현재 눌린 노트 트래킹

for track in midi.tracks:
    current_tick = 0
    for msg in track:
        current_tick += msg.time

        if msg.type == "note_on" and msg.velocity > 0:
            active_notes.setdefault(msg.note, []).append(current_tick)
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            if msg.note in active_notes and active_notes[msg.note]:
                start_tick = active_notes[msg.note].pop(0)
                note_events.setdefault(msg.note, []).append({
                    "start_tick": start_tick,
                    "end_tick": current_tick
                })

# === 노트별 오디오 추출 및 WAV ID 할당 ===
wav_id_map = {}
wav_counter = 1

for note, evs in sorted(note_events.items()):
    for ev in evs:
        start_s = tick_to_seconds(ev["start_tick"])
        end_s = tick_to_seconds(ev["end_tick"])
        if end_s <= start_s:
            continue

        start_ms, end_ms = start_s * 1000, end_s * 1000
        clip = audio[start_ms:end_ms]
        if len(clip) < 10:
            continue

        out_name = f"note_{wav_counter:02}.wav"
        clip.export(os.path.join(output_dir, out_name), format="wav")
        wav_id_map[(note, ev["start_tick"])] = f"{wav_counter:02}"
        print(f"Saved note {note} → {out_name}")
        wav_counter += 1

# === BPM 계산 ===
last_tempo = tempo_events[-1][1]
bpm = 60000000 / last_tempo

# === 4KEY 레인 매핑 예시 (C4~F4 기준) ===
lane_map = {60:1, 62:2, 64:3, 65:4}  # 필요시 MIDI 음에 맞춰 수정

# === BMS/BMA 헤더 생성 ===
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
for wav_id in sorted(set(wav_id_map.values())):
    header.append(f"#WAV{wav_id} {output_dir}/note_{wav_id}.wav")
header.append("*---------------------- MAIN DATA FIELD")

# === BMS 본문 생성 ===
bms_lines = []
for note, evs in note_events.items():
    for ev in evs:
        start_time = tick_to_seconds(ev["start_tick"])
        measure = int((start_time * bpm / 60) / 4)
        pos_in_measure = ((start_time * bpm / 60) % 4) / 4
        position = int(pos_in_measure * 192)

        lane = lane_map.get(note, 1)
        channel = 10 + lane
        wav_id = wav_id_map.get((note, ev["start_tick"]), "01")

        bms_lines.append(f"#{measure:03d}{channel:02d}:{'00'*position}{wav_id}{'00'*(192-position-1)}")

# === 파일 저장 ===
with open(bms_path, "w", encoding="utf-8") as f:
    f.write("\n".join(header + bms_lines))
print(f"✅ BMS 파일 저장 완료: {bms_path}")

with open(bma_path, "w", encoding="utf-8") as f:
    f.write("\n".join(header + bms_lines))
print(f"✅ BMA 파일 저장 완료: {bma_path}")
