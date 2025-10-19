from mido import MidiFile, MidiTrack, MetaMessage
import os

def split_by_layer(input_path, output_dir):
    mid = MidiFile(input_path)
    os.makedirs(output_dir, exist_ok=True)

    # 전체 이벤트를 absolute 시간으로 정렬
    events = []
    for tr in mid.tracks:
        abs_time = 0
        for msg in tr:
            abs_time += msg.time
            events.append((abs_time, msg))
    events.sort(key=lambda e: e[0])
    total_length = events[-1][0] if events else 0

    # Layer(=동시 note 그룹)
    layers = []
    layer_active_notes = []  # 각 layer의 활성 note 상태
    layer_last_time = []

    for abs_time, msg in events:
        if msg.type not in ('note_on', 'note_off'):
            continue

        # note_on인 경우
        if msg.type == 'note_on' and msg.velocity > 0:
            # 빈 layer 찾기 (겹치지 않는 곳)
            assigned = False
            for i, active in enumerate(layer_active_notes):
                if len(active) == 0:  # 비어 있는 layer
                    layers[i].append((abs_time, msg))
                    active.add(msg.note)
                    layer_last_time[i] = abs_time
                    assigned = True
                    break
            if not assigned:
                # 새 layer 생성
                layers.append([(abs_time, msg)])
                layer_active_notes.append({msg.note})
                layer_last_time.append(abs_time)

        elif msg.type == 'note_off':
            # note_off일 때 해당 note가 켜진 layer 찾기
            for i, active in enumerate(layer_active_notes):
                if msg.note in active:
                    delta = abs_time - layer_last_time[i]
                    layers[i].append((abs_time, msg))
                    layer_last_time[i] = abs_time
                    active.remove(msg.note)
                    break

    # === 각 layer를 개별 MIDI 파일로 저장 ===
    for i, layer_events in enumerate(layers):
        out = MidiFile()
        out.ticks_per_beat = mid.ticks_per_beat

        tr = MidiTrack()
        out.tracks.append(tr)

        # 템포, 메타 복사
        for msg in mid.tracks[0]:
            if msg.is_meta:
                tr.append(msg.copy(time=0))

        last_time = 0
        for abs_time, msg in layer_events:
            delta = abs_time - last_time
            tr.append(msg.copy(time=delta))
            last_time = abs_time

        if last_time < total_length:
            tr.append(MetaMessage('end_of_track', time=total_length - last_time))
        else:
            tr.append(MetaMessage('end_of_track', time=0))

        filename = os.path.join(output_dir, f"layer_{i+1:02d}.mid")
        out.save(filename)
        print(f"🎵 Saved {filename}")

    print(f"\n✅ 총 {len(layers)}개의 Layer MIDI 파일 생성 완료 (폴더: {output_dir})")


# 사용 예시
split_by_layer("input.mid", "split_layers")
