@forelse ($cabinets as $cabinet)
<div
    class="manage-row"
    data-id="{{ $cabinet['id'] }}"
    data-name="{{ $cabinet['name'] ?? '' }}"
    data-location="{{ $cabinet['location'] ?? '' }}"
    data-description="{{ $cabinet['description'] ?? '' }}"
    data-capacity="{{ $cabinet['capacity'] ?? '' }}"
    data-laptop-count="{{ $cabinet['laptop_count'] }}"
>
    <label class="manage-row-main">
        <input class="manage-checkbox" type="checkbox" value="{{ $cabinet['id'] }}">
        <span>
            <span class="manage-name">{{ $cabinet['name'] }}</span>
            <span class="manage-meta">
                @if ($cabinet['location']){{ $cabinet['location'] }}@else—@endif
                |
                @if ($cabinet['capacity'] !== null)
                  Bezetting: {{ $cabinet['laptop_count'] }}/{{ $cabinet['capacity'] }}
                @else
                  Bezetting: {{ $cabinet['laptop_count'] }}
                @endif
                @if ($cabinet['description']) | {{ $cabinet['description'] }}@endif
            </span>
        </span>
    </label>
    <div class="manage-row-actions">
        <button class="btn sm" type="button" onclick="cabinetManageEdit(this)">Bewerk</button>
        <button class="btn sm danger" type="button"
                onclick="cabinetManageDelete({{ $cabinet['id'] }}, '{{ $cabinet['name'] }}')">✕</button>
    </div>
</div>
@empty
<p style="padding:16px; color:var(--muted);">Geen locaties gevonden.</p>
@endforelse
