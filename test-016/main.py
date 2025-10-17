from mido import MidiFile, MidiTrack, Message, MetaMessage

def split_overlapping_notes(input_path):
    midi = MidiFile(input_path)
    out = MidiFile()
    out.ticks_per_beat = midi.ticks_per_beat

    # 트랙0 메타 복사
    meta_track = MidiTrack()
    for msg in midi.tracks[0]:
        if msg.is_meta:
            meta_track.append(msg.copy())
    out.tracks.append(meta_track)

    # 모든 노트 이벤트를 절대시간으로 수집
    events = []
    for tr in midi.tracks:
        t = 0
        for msg in tr:
            t += msg.time
            if not msg.is_meta:
                events.append((t, msg))

    # note_on/note_off 쌍 매칭
    stack = {}
    notes = []
    for abs_time, msg in sorted(events, key=lambda e: e[0]):
        if msg.type == "note_on" and msg.velocity > 0:
            stack.setdefault((msg.note, msg.channel), []).append(abs_time)
        elif msg.type in ("note_off", "note_on") and msg.velocity == 0:
            key = (msg.note, msg.channel)
            if key in stack and stack[key]:
                start = stack[key].pop(0)
                notes.append({
                    "start": start,
                    "end": abs_time,
                    "note": msg.note,
                    "velocity": msg.velocity if msg.type == "note_on" else 64,
                    "channel": msg.channel
                })

    # 겹치지 않게 최소 트랙으로 분배
    notes.sort(key=lambda n: n["start"])
    tracks = []  # 각 트랙은 마지막 노트 끝 시간 저장
    track_notes = []  # 각 트랙의 노트 리스트

    for n in notes:
        assigned = False
        for i, end_time in enumerate(tracks):
            if n["start"] >= end_time:  # 겹치지 않음
                tracks[i] = n["end"]
                track_notes[i].append(n)
                assigned = True
                break
        if not assigned:
            tracks.append(n["end"])
            track_notes.append([n])

    print(f"총 {len(track_notes)}개 트랙으로 분리됨")

    # 각 트랙별로 MIDITrack 생성
    for i, notes_in_track in enumerate(track_notes):
        tr = MidiTrack()
        abs_time = 0
        events = []
        for n in notes_in_track:
            events.append((n["start"], "on", n))
            events.append((n["end"], "off", n))
        events.sort(key=lambda e: (e[0], 0 if e[1]=="on" else 1))
        for t, typ, n in events:
            delta = t - abs_time
            abs_time = t
            if typ == "on":
                tr.append(Message("note_on", note=n["note"], velocity=64, time=delta, channel=n["channel"]))
            else:
                tr.append(Message("note_off", note=n["note"], velocity=0, time=delta, channel=n["channel"]))
        out.tracks.append(tr)

    # 전체 합친 파일 저장
    out.save("output_combined.mid")

    # 트랙별로 개별 저장
    for i, tr in enumerate(out.tracks[1:], start=0):
        single = MidiFile()
        single.ticks_per_beat = midi.ticks_per_beat
        single.tracks.append(meta_track.copy())
        single.tracks.append(tr.copy())
        single.save(f"output_track_{i}.mid")

    print("✅ 저장 완료: output_combined.mid 및 output_track_*.mid")

# 실행
split_overlapping_notes("input.mid")
