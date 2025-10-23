from mido import MidiFile
from pydub import AudioSegment
import os
import re

# === 설정 ===
midi_files = ["pn1.mid", "pn2.mid", "pn3.mid",
              "pn4.mid", "pn5.mid", "kick.mid", "snare.mid"]
wav_files = ["pn1.wav", "pn2.wav", "pn3.wav",
             "pn4.wav", "pn5.wav", "kick.wav", "snare.wav"]
instrument_names = ["pn1", "pn2", "pn3", "pn4", "pn5", "kick", "snare"]

output_dir = "notes"
bms_path = "output.bms"
bpm_default = 96
division = 48
base_lane = 11
min_note_ms = 50

os.makedirs(output_dir, exist_ok=True)

# 36진수 변환
digits36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
def to36(n):
    return digits36[n] if n < 36 else digits36[n//36] + digits36[n%36]

# --- BMS 초기화 ---
if not os.path.exists(bms_path):
    header = [
        "*---------------------- HEADER FIELD",
        "#PLAYER 1",
        "#GENRE AUTO_MERGE",
        "#TITLE COMBINED MIDI",
        "#ARTIST AI",
        f"#BPM {bpm_default}",
        "#PLAYLEVEL 1",
        "#RANK 2",
        "#LNTYPE 0",
        "*---------------------- MAIN DATA FIELD"
    ]
    with open(bms_path, "w", encoding="utf-8") as f:
        f.write("\n".join(header))

# --- 기존 BMS 읽기 ---
with open(bms_path, "r", encoding="utf-8") as f:
    bms_lines = f.read().splitlines()

# 기존 measure_data 초기화
measure_data = {}
for line in bms_lines:
    m = re.match(r"#(\d{3})(\d{2}):(.*)", line)
    if m:
        measure = int(m.group(1))
        channel = m.group(2)
        data = list(re.findall("..", m.group(3)))
        measure_data.setdefault(measure, {})[channel] = data

# --- MIDI + WAV 병합 ---
next_wav_index = 1  # BMS WAV 번호 01부터 시작
instrument_file_counter = {name:1 for name in instrument_names}  # 파일명 악기별 순번

for idx, (midi_path, wav_path, inst_name) in enumerate(zip(midi_files, wav_files, instrument_names)):
    if not os.path.exists(midi_path) or not os.path.exists(wav_path):
        continue

    lane_channel = f"{base_lane + idx:02}"
    mid = MidiFile(midi_path)
    ticks_per_beat = mid.ticks_per_beat
    def tick_to_sec(t): return (t / ticks_per_beat) * (60 / bpm_default)
    audio = AudioSegment.from_file(wav_path)

    # --- MIDI note 추출 ---
    notes = []
    for track in mid.tracks:
        current_tick = 0
        for msg in track:
            current_tick += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                notes.append(current_tick)
    notes.sort()

    # --- WAV 추출 및 중복 최소화 ---
    note_map = {}  # (length_ms) -> BMS WAV 번호
    event_list = []

    for i, tick_start in enumerate(notes):
        start_sec = tick_to_sec(tick_start)
        tick_end = notes[i+1] if i+1 < len(notes) else mid.length
        end_sec = tick_to_sec(tick_end)
        length_ms = max(int((end_sec - start_sec)*1000), min_note_ms)

        key = length_ms
        if key not in note_map:
            wav_num = instrument_file_counter[inst_name]
            filename = os.path.join(output_dir, f"{inst_name}-{wav_num:02}.wav")
            segment = audio[int(start_sec*1000):int(start_sec*1000)+length_ms]
            segment.export(filename, format="wav")

            note_map[key] = next_wav_index
            next_wav_index += 1
            instrument_file_counter[inst_name] += 1
        wav_id = note_map[key]
        event_list.append((start_sec, wav_id))

    # --- WAV 등록 ---
    existing_wavs = {m.group(1) for line in bms_lines if (m:=re.match(r"#WAV([0-9A-Z]{2})", line))}
    insert_index = next((i for i, l in enumerate(bms_lines) if l.startswith("*---------------------- MAIN DATA FIELD")), len(bms_lines))

    for length_ms, wav_id in sorted(note_map.items(), key=lambda x: x[1]):
        wav36 = to36(wav_id)
        if wav36 not in existing_wavs:
            file_num = instrument_file_counter[inst_name]-1  # 방금 생성한 마지막 번호
            filename = f"{output_dir}/{inst_name}-{file_num:02}.wav"
            bms_lines.insert(insert_index, f"#WAV{wav36:02} {filename}")
            existing_wavs.add(wav36)

    # --- 마디별 배치 ---
    bar_duration = (60 / bpm_default) * 4
    for start_sec, wav_id in event_list:
        measure = int(start_sec // bar_duration)
        div = int((start_sec % bar_duration) / bar_duration * division)
        if measure not in measure_data:
            measure_data[measure] = {}
        if lane_channel not in measure_data[measure]:
            measure_data[measure][lane_channel] = ["00"] * division
        measure_data[measure][lane_channel][div] = f"{to36(wav_id):02}"

# --- MAIN DATA 재구성 ---
main_data = ["*---------------------- MAIN DATA FIELD"]
for measure in sorted(measure_data.keys()):
    for channel in sorted(measure_data[measure].keys()):
        data = "".join(measure_data[measure][channel])
        main_data.append(f"#{measure:03}{channel}:{data}")

# --- BMS 저장 ---
with open(bms_path, "w", encoding="utf-8") as f:
    for line in bms_lines:
        if not line.startswith("#") or not re.match(r"#\d{3}\d{2}:", line):
            f.write(line + "\n")
    f.write("\n".join(main_data))

print("🎉 모든 MIDI 병합 완료! (악기별 순차 파일명, BMS WAV 번호 01부터 시작)")
