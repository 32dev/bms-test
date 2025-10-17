from pydub import AudioSegment
from mido import MidiFile, tick2second

midi = MidiFile("song.mid")
audio = AudioSegment.from_file("song.wav")

ticks_per_beat = midi.ticks_per_beat
tempo = 500000  # 기본 템포 (120 BPM)

note_segments = {}

for i, track in enumerate(midi.tracks):
    current_tick = 0
    for msg in track:
        current_tick += msg.time

        if msg.type == "set_tempo":
            tempo = msg.tempo

        elif msg.type == "note_on":
            note = msg.note
            start_ms = tick2second(current_tick, ticks_per_beat, tempo) * 1000

            # velocity > 0 = 노트 시작
            if msg.velocity > 0:
                # 이전 노트가 끝나지 않았다면 강제로 닫기
                if note in note_segments and len(note_segments[note]) == 1:
                    note_segments[note].append(start_ms)
                note_segments[note] = [start_ms]

            # velocity == 0 = 노트 종료
            else:
                if note in note_segments and len(note_segments[note]) == 1:
                    end_ms = start_ms
                    note_segments[note].append(end_ms)

        elif msg.type == "note_off":
            note = msg.note
            end_ms = tick2second(current_tick, ticks_per_beat, tempo) * 1000
            if note in note_segments and len(note_segments[note]) == 1:
                note_segments[note].append(end_ms)

# === note별 오디오 자르기 ===
for note, times in note_segments.items():
    if len(times) < 2:
        print(f"Skipping note {note} (no end time)")
        continue

    start, end = times
    start = int(start)
    end = int(end)
    if end > start:
        segment = audio[start:end]
        segment.export(f"note_{note}.wav", format="wav")
        print(f"Saved: note_{note}.wav ({end - start:.1f} ms)")
