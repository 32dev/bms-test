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

    # absolute 시간 기반 이벤트 수집
    events = []
    for tr in mid.tracks:
        abs_time = 0
        for msg in tr:
            abs_time += msg.time
            events.append((abs_time, msg))
    events.sort(key=lambda e: e[0])
    total_length = events[-1][0] if events else 0  # 전체 MIDI 길이 tick

    pitch_tracks = {}   # pitch -> [track1, track2, ...]
    last_time = {}      # (pitch, track_idx) -> last_abs_tick
    active_track_for_pitch = {}  # pitch -> track_idx (현재 note_on 활성 트랙)

    for abs_time, msg in events:
        if msg.type in ('note_on', 'note_off'):
            pitch = msg.note
            if pitch not in pitch_tracks:
                pitch_tracks[pitch] = []
                active_track_for_pitch[pitch] = None

            if msg.type == 'note_on' and msg.velocity > 0:
                # 활성 트랙 찾기 (겹치면 새로)
                track_idx = active_track_for_pitch.get(pitch)
                if track_idx is not None:
                    # 이미 켜진 note 존재 => 새로운 트랙 생성
                    track_idx = None
                if track_idx is None:
                    # 재활용 가능한 트랙 찾기
                    for i, tr in enumerate(pitch_tracks[pitch]):
                        if active_track_for_pitch.get((pitch, i)) is None:
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

            else:  # note_off
                track_idx = active_track_for_pitch.get(pitch)
                if track_idx is not None:
                    tr = pitch_tracks[pitch][track_idx]
                    delta = abs_time - last_time[(pitch, track_idx)]
                    tr.append(msg.copy(time=delta))
                    last_time[(pitch, track_idx)] = abs_time
                    active_track_for_pitch[pitch] = None

    # === 전체 길이 보정 ===
    for pitch, tracks in pitch_tracks.items():
        for i, tr in enumerate(tracks):
            end_time = last_time.get((pitch, i), 0)
            if end_time < total_length:
                delta = total_length - end_time
                tr.append(MetaMessage('end_of_track', time=delta))
            else:
                tr.append(MetaMessage('end_of_track', time=0))

    # 메타트랙도 end_of_track 보정
    meta_track.append(MetaMessage('end_of_track', time=0))

    out.save(output_path)
    print(f"✅ Saved: {output_path} (전체 길이 {total_length} ticks 유지)")


# 사용 예시
split_by_pitch("input.mid", "split_by_pitch_full_length.mid")
