from mido import MidiFile, MidiTrack, Message, MetaMessage
import os

def split_by_pitch(input_path, output_dir):
    mid = MidiFile(input_path)
    os.makedirs(output_dir, exist_ok=True)

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

    # === 트랙 생성 ===
    for abs_time, msg in events:
        if msg.type in ('note_on', 'note_off'):
            pitch = msg.note
            if pitch not in pitch_tracks:
                pitch_tracks[pitch] = []
                active_track_for_pitch[pitch] = None

            if msg.type == 'note_on' and msg.velocity > 0:
                track_idx = active_track_for_pitch.get(pitch)
                if track_idx is not None:
                    track_idx = None
                if track_idx is None:
                    for i, tr in enumerate(pitch_tracks[pitch]):
                        if active_track_for_pitch.get((pitch, i)) is None:
                            track_idx = i
                            break
                    if track_idx is None:
                        tr = MidiTrack()
                        pitch_tracks[pitch].append(tr)
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

    # === 개별 MIDI 파일로 저장 ===
    for pitch, tracks in pitch_tracks.items():
        for i, tr in enumerate(tracks):
            out = MidiFile()
            out.ticks_per_beat = mid.ticks_per_beat

            meta_track = MidiTrack()
            for msg in mid.tracks[0]:
                if msg.is_meta:
                    meta_track.append(msg.copy(time=0))
            meta_track.append(MetaMessage('end_of_track', time=0))
            out.tracks.append(meta_track)

            end_time = last_time.get((pitch, i), 0)
            if end_time < total_length:
                delta = total_length - end_time
                tr.append(MetaMessage('end_of_track', time=delta))
            else:
                tr.append(MetaMessage('end_of_track', time=0))
            out.tracks.append(tr)

            filename = os.path.join(output_dir, f"note_{pitch}_track{i+1}.mid")
            out.save(filename)
            print(f"🎵 Saved {filename}")

    print(f"\n✅ 총 {sum(len(v) for v in pitch_tracks.values())}개의 MIDI 파일 생성 완료 (폴더: {output_dir})")


# 사용 예시
split_by_pitch("input.mid", "split_pitch_mid_files")
