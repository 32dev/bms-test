from mido import MidiFile, MidiTrack, Message, MetaMessage

def split_by_pitch(input_path, output_path):
    mid = MidiFile(input_path)
    out = MidiFile()
    out.ticks_per_beat = mid.ticks_per_beat

    # 메타 트랙 복사
    meta_track = MidiTrack()
    for msg in mid.tracks[0]:
        if msg.is_meta:
            meta_track.append(msg.copy())
    out.tracks.append(meta_track)

    # absolute 시간 기반으로 모든 이벤트 수집
    events = []
    for tr in mid.tracks:
        abs_time = 0
        for msg in tr:
            abs_time += msg.time
            events.append((abs_time, msg))
    events.sort(key=lambda e: e[0])

    # pitch별 여러 트랙 관리
    pitch_tracks = {}   # pitch -> [track1, track2, ...]
    last_time = {}      # (pitch, track_idx) -> last_abs_tick
    active_track_for_pitch = {}  # pitch -> track_idx (현재 note_on이 켜진 트랙 인덱스)

    for abs_time, msg in events:
        if msg.type in ('note_on', 'note_off'):
            pitch = msg.note
            if pitch not in pitch_tracks:
                pitch_tracks[pitch] = []
                active_track_for_pitch[pitch] = None

            # note_on일 때
            if msg.type == 'note_on' and msg.velocity > 0:
                # 현재 활성 트랙이 없거나 이미 note_on 상태이면 새 트랙 생성
                if active_track_for_pitch[pitch] is not None:
                    # 기존 트랙이 note_off 안 된 상태이므로 새 트랙
                    pass
                # 새로운 트랙 선택 (없거나 기존 note_on중첩시 새로)
                track_idx = None
                # 사용 가능한 트랙 찾기 (현재 note_off된 것)
                for i, tr in enumerate(pitch_tracks[pitch]):
                    if (pitch, i) not in active_track_for_pitch.values():
                        track_idx = i
                        break
                if track_idx is None:
                    # 새 트랙 생성
                    tr = MidiTrack()
                    pitch_tracks[pitch].append(tr)
                    out.tracks.append(tr)
                    track_idx = len(pitch_tracks[pitch]) - 1
                    last_time[(pitch, track_idx)] = 0

                active_track_for_pitch[pitch] = track_idx
                tr = pitch_tracks[pitch][track_idx]

                delta = abs_time - last_time[(pitch, track_idx)]
                tr.append(msg.copy(time=delta))
                last_time[(pitch, track_idx)] = abs_time

            # note_off일 때
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                track_idx = active_track_for_pitch.get(pitch)
                if track_idx is not None:
                    tr = pitch_tracks[pitch][track_idx]
                    delta = abs_time - last_time[(pitch, track_idx)]
                    tr.append(msg.copy(time=delta))
                    last_time[(pitch, track_idx)] = abs_time
                    active_track_for_pitch[pitch] = None  # note 종료

    out.save(output_path)
    print(f"Saved: {output_path}")


# 사용 예시
split_by_pitch("input.mid", "split_by_pitch_single_note.mid")
