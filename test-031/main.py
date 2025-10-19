from pydub import AudioSegment
from mido import MidiFile
import os

# === 설정 ===
midi_path = "song.mid"
wav_path = "song.wav"
bgm_wav_path = "bgm.wav"  # 백그라운드 사운드
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
tempo_events = [(0, tempo)]

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

# === 모든 노트 시간 수집 ===
note_events = {}
active_notes = {}

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

# === B1~B15 레인 매핑 ===
unique_notes = sorted(note_events.keys())
lane_map = {}
for i, note in enumerate(unique_notes):
    lane_map[note] = (i % 15) + 1  # B1~B15 반복

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

# 백그라운드 WAV 등록 (WAV00)
header.append(f"#WAV00 {bgm_wav_path}")
for wav_id in sorted(set(wav_id_map.values())):
    header.append(f"#WAV{wav_id} {output_dir}/note_{wav_id}.wav")
header.append("*---------------------- MAIN DATA FIELD")

# === BMS 본문 생성 (B1~B15, 192분할 안전 처리) ===
main_data = {}

# 노트 배치
for note, evs in note_events.items():
    for ev in evs:
        start_time = tick_to_seconds(ev["start_tick"])
        measure = int((start_time * bpm / 60) / 4)
        pos_in_measure = ((start_time * bpm / 60) % 4) / 4
        position = int(pos_in_measure * 192)
        position = min(max(position, 0), 191)  # 안전 클램프

        lane = lane_map.get(note, 1)
        channel = f"B{lane}"
        wav_id = wav_id_map.get((note, ev["start_tick"]), "01")

        key = (measure, channel)
        if key not in main_data:
            main_data[key] = ['00'] * 192
        main_data[key][position] = wav_id

# MAIN DATA FIELD 문자열 변환
bms_lines = []

# 백그라운드 사운드 BGM 배치 (B0 채널, WAV00, 첫 마디 시작)
bgm_line = f"#00001:B0:{'00'*191}00"  # 192분할, 마지막 '00' = WAV00
bms_lines.append(bgm_line)

# 노트 라인 추가, 마디와 채널 기준 정렬
for (measure, channel), data in sorted(main_data.items(), key=lambda x: (x[0][0], int(x[0][1][1:]))):
    line = f"#{measure:03d}{channel}:{''.join(data)}"
    bms_lines.append(line)

# === 파일 저장 ===
with open(bms_path, "w", encoding="utf-8") as f:
    f.write("\n".join(header + bms_lines))
print(f"✅ BMS 파일 저장 완료: {bms_path}")

with open(bma_path, "w", encoding="utf-8") as f:
    f.write("\n".join(header + bms_lines))
print(f"✅ BMA 파일 저장 완료: {bma_path}")
