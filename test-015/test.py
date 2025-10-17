from mido import MidiFile, MidiFile, MidiTrack, Message, MetaMessage

def split_by_pitch(input_path, output_path):
    mid = MidiFile(input_path)
    out = MidiFile()
    out.ticks_per_beat = mid.ticks_per_beat

    # 트랙별로 마지막 absolute tick을 저장해 delta 계산에 사용
    track_last_time = {}  # pitch -> last_abs_tick
    pitch_tracks = {}     # pitch -> MidiTrack

    # 기본 메타메시지(템포, time signature 등)는 원본 트랙 0에서 복사
    meta_track = MidiTrack()
    # 합쳐서 나머지 트랙들 앞에 넣기
    for msg in mid.tracks[0]:
        if msg.is_meta:
            meta_track.append(msg.copy())
    out.tracks.append(meta_track)

    # 전체원본을 absolute tick으로 읽음 (합쳐진 시퀀스처럼)
    # 여러 트랙 존재할 수 있으므로, 먼저 모든 메시지를 absolute시간 순으로 모아 정렬
    events = []
    for i, tr in enumerate(mid.tracks):
        abs_time = 0
        for msg in tr:
            abs_time += msg.time
            events.append((abs_time, msg, i))
    # 시간순 정렬
    events.sort(key=lambda e: e[0])

    for abs_time, msg, orig_track_idx in events:
        if not msg.is_meta and msg.type in ('note_on', 'note_off'):
            pitch = msg.note
            if pitch not in pitch_tracks:
                pitch_tracks[pitch] = MidiTrack()
                # 처음 만들 때 초기 delta 0
                track_last_time[pitch] = 0
                out.tracks.append(pitch_tracks[pitch])

            # compute delta relative to last event in that pitch-track
            delta = abs_time - track_last_time[pitch]
            # append same message but with delta in that track
            new_msg = msg.copy(time=delta)
            pitch_tracks[pitch].append(new_msg)
            track_last_time[pitch] = abs_time
        else:
            # meta나 다른 컨트롤 메시지: (선택) 트랙0(메타 트랙)에 이미 복사했으므로 무시
            pass

    out.save(output_path)


# 사용 예
split_by_pitch('input.mid', 'by_pitch.mid')
