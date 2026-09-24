@forelse ($laptops as $laptop)
@php($inCabinet = $laptop['storage_cabinet_id'] !== null)
<tr class="lt-manage-row"
    data-id="{{ $laptop['id'] }}"
    data-is-reserve="{{ $laptop['is_reserve'] ? '1' : '0' }}"
    data-in-cabinet="{{ $inCabinet ? '1' : '0' }}"
    data-cabinet-id="{{ $laptop['storage_cabinet_id'] ?: '' }}">
  <td class="lt-manage-serial">
    <span class="lt-manage-display">
      @if ($laptop['eigen_laptop'])
        <em style="color:var(--muted)">eigen laptop</em>
      @else
        {{ $laptop['serial_number'] ?: '—' }}
      @endif
    </span>
    <input class="input lt-manage-edit-serial" type="text"
           value="{{ $laptop['serial_number'] ?: '' }}"
           style="display:none;" placeholder="Serienummer">
  </td>
  <td class="lt-manage-student">
    <span class="lt-manage-display">
      @if ($inCabinet)
        @if ($laptop['cabinet_kind'] === 'magazijn')
          <span class="badge" style="background:var(--accent); color:#fff;">Magazijn</span>
        @else
          <span class="badge" style="background:var(--accent); color:#fff;">Kast</span>
        @endif
        <strong style="margin-left:6px;">{{ $laptop['cabinet_name'] }}</strong>
        @if ($laptop['cabinet_location'])
          <small style="color:var(--muted)"> ({{ $laptop['cabinet_location'] }})</small>
        @endif
      @elseif ($laptop['is_reserve'])
        <span class="badge" style="background:var(--accent); color:#fff;">Reserve</span>
        @if ($laptop['alias'])
          <strong style="margin-left:6px;">{{ $laptop['alias'] }}</strong>
        @endif
      @elseif ($laptop['naam'])
        {{ $laptop['voornaam'] }} {{ $laptop['naam'] }}
        <small style="color:var(--muted)"> {{ $laptop['stamnummer'] }}</small>
      @else
        —@if ($laptop['stamnummer']) <small style="color:var(--muted)"> {{ $laptop['stamnummer'] }}</small>@endif
      @endif
    </span>
    @if ($laptop['is_reserve'])
      <input class="input lt-manage-edit-alias" type="text"
             value="{{ $laptop['alias'] ?: '' }}"
             style="display:none;" placeholder="Alias">
    @elseif (! $inCabinet)
      <input class="input lt-manage-edit-stamnummer" type="text"
             value="{{ $laptop['stamnummer'] ?: '' }}"
             style="display:none;" placeholder="Stamnummer">
    @endif
  </td>
  <td>@if ($laptop['is_reserve'] || $inCabinet)—@else{{ $laptop['klas'] ?: '—' }}@endif</td>
  <td>
    <span class="badge {{ $laptop['is_active'] ? 'badge-active' : 'badge-old' }}">
      {{ $laptop['is_active'] ? 'Actief' : 'Inactief' }}
    </span>
  </td>
  <td style="font-size:12px; white-space:nowrap;">
    @if ($laptop['is_active'] || $laptop['is_reserve'] || $inCabinet || $laptop['eigen_laptop'])
      <span style="color:var(--muted);">—</span>
    @else
      <span title="Beschermhoes bij laatste inlevering"
            style="color: {{ $laptop['hoes_ingeleverd'] ? 'var(--success, #2e7d32)' : 'var(--danger, #c62828)' }};">
        {{ $laptop['hoes_ingeleverd'] ? '✓' : '✕' }} hoes
      </span>
      <span title="Oplader bij laatste inlevering"
            style="margin-left:8px; color: {{ $laptop['oplader_ingeleverd'] ? 'var(--success, #2e7d32)' : 'var(--danger, #c62828)' }};">
        {{ $laptop['oplader_ingeleverd'] ? '✓' : '✕' }} oplader
      </span>
    @endif
  </td>
  <td style="color:var(--muted); font-size:12px;">
    {{ $laptop['linked_at'] ? $laptop['linked_at']->format('d/m/Y') : '—' }}
  </td>
  <td class="lt-manage-actions">
    <button class="btn sm lt-manage-btn-edit" type="button"
            onclick="ltManageEdit(this)">Bewerk</button>
    <button class="btn sm lt-manage-btn-save" type="button"
            style="display:none;"
            onclick="ltManageSave(this, {{ $laptop['id'] }})">Opslaan</button>
    <button class="btn sm lt-manage-btn-cancel" type="button"
            style="display:none;"
            onclick="ltManageCancel(this)">Annuleer</button>
    <button class="btn sm danger lt-manage-btn-delete" type="button"
            onclick="ltManageDelete(this, {{ $laptop['id'] }}, '{{ $laptop['alias'] ?: ($laptop['serial_number'] ?: 'eigen laptop') }}')">✕</button>
  </td>
</tr>
@empty
<tr><td colspan="7" style="padding:16px; color:var(--muted); text-align:center;">Geen laptops gevonden.</td></tr>
@endforelse
