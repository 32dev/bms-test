from mido import MidiFile

midi = MidiFile("song.mid")

print(f"🎵 MIDI 파일 구조 분석")
print(f"파일 형식: Type {midi.type}")
print(f"트랙 수: {len(midi.tracks)}")
print(f"Ticks per beat: {midi.ticks_per_beat}")
print("=" * 60)

for i, track in enumerate(midi.tracks):
    print(f"\n🎶 Track {i}: {track.name if track.name else '(이름 없음)'}")
    current_tick = 0
    note_on_count = 0
    note_off_count = 0

    for msg in track:
        current_tick += msg.time

        # note 관련 메시지 필터링
        if msg.type in ("note_on", "note_off"):
            time_in_ticks = current_tick
            time_in_ms = round(midi.ticks_per_beat * time_in_ticks / 480, 2)
            print(f"  {msg}  (누적 tick: {current_tick})")
            if msg.type == "note_on" and msg.velocity > 0:
                note_on_count += 1
            else:
                note_off_count += 1

    print(f"  ▶ note_on 개수: {note_on_count}")
    print(f"  ▶ note_off/velocity0 개수: {note_off_count}")

print("\n✅ 분석 완료")