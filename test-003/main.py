from pydub import AudioSegment
from mido import MidiFile, tick2second

# MIDI / 오디오 파일 불러오기
midi = MidiFile("song.mid")
audio = AudioSegment.from_file("song.wav")

ticks_per_beat = midi.ticks_per_beat
tempo = 500000  # 기본 템포 (120 BPM)

note_segments = {}

# 🎵 각 트랙별 이벤트 분석
for i, track in enumerate(midi.tracks):
    current_tick = 0
    for msg in track:
        current_tick += msg.time

        # 템포 변경 이벤트 처리
        if msg.type == "set_tempo":
            tempo = msg.tempo

        # 노트 ON (음 시작)
        elif msg.type == "note_on" and msg.velocity > 0:
            note = msg.note
            start_ms = tick2second(current_tick, ticks_per_beat, tempo) * 1000
            note_segments[note] = [start_ms]

        # 노트 OFF (음 끝)
        elif msg.type in ("note_off", "note_on") and msg.velocity == 0:
            note = msg.note
            end_ms = tick2second(current_tick, ticks_per_beat, tempo) * 1000
            if note in note_segments and len(note_segments[note]) == 1:
                note_segments[note].append(end_ms)

# 🎧 노트별 오디오 자르기
for note, times in note_segments.items():
    if len(times) < 2:
        print(f"Skipping note {note} (no end time)")
        continue

    start, end = times
    start = int(start)
    end = int(end)

    # 구간 잘라내기 및 저장
    if end > start:
        segment = audio[start:end]
        segment.export(f"note_{note}.wav", format="wav")
        print(f"Saved: note_{note}.wav ({end - start:.1f} ms)")
