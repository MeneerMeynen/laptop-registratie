@forelse ($students as $student)
@php
    $groupLatest = $latest_import_at[$student->is_leerkracht ? 1 : 0];
    $isOld = $groupLatest && $student->last_import && $student->last_import->lt($groupLatest);
    $hasEigen = $student->laptops->contains(fn ($l) => $l->eigen_laptop);
    $hasSerial = $student->laptops->contains(fn ($l) => ! $l->eigen_laptop && $l->serial_number);
    $manageFilter = ($student->is_leerkracht ? 'leerkracht ' : '').implode(' ', [
        $student->afkorting, $student->instellingsnummer, $student->naam, $student->voornaam, $student->klas,
        $student->klascode, $student->klasnummer, $student->gebruikersnaam, $student->pointer, $student->stamnummer,
    ]);
    $laptopFlags = trim(($hasEigen ? 'eigen ' : '').($hasSerial ? 'met ' : '').(($hasEigen || $hasSerial) ? '' : 'zonder'));
@endphp
<div
    class="manage-row"
    data-manage-filter="{{ $manageFilter }}"
    data-old-import="{{ $isOld ? 'true' : 'false' }}"
    data-group="{{ $student->is_leerkracht ? 'leerkracht' : 'leerling' }}"
    data-laptop="{{ $laptopFlags }}"
    data-stamnummer="{{ $student->stamnummer }}"
    data-instellingsnummer="{{ $student->instellingsnummer ?? '' }}"
    data-naam="{{ $student->naam ?? '' }}"
    data-voornaam="{{ $student->voornaam ?? '' }}"
    data-klas="{{ $student->klas ?? '' }}"
    data-klascode="{{ $student->klascode ?? '' }}"
    data-klasnummer="{{ $student->klasnummer ?? '' }}"
    data-gebruikersnaam="{{ $student->gebruikersnaam ?? '' }}"
    data-pointer="{{ $student->pointer ?? '' }}"
    data-afkorting="{{ $student->afkorting ?? '' }}"
>
    <label class="manage-row-main">
        <input class="manage-checkbox" type="checkbox" value="{{ $student->stamnummer }}">
        <span>
            <span class="manage-name">{{ $student->naam }}, {{ $student->voornaam }}</span>
            <span class="manage-meta">{{ $student->klas ?: ($student->afkorting ?: ($student->is_leerkracht ? 'Leerkracht' : '')) }} | {{ $student->stamnummer }} | {{ $student->gebruikersnaam }}</span>
            @if ($student->is_leerkracht)
            <span class="badge badge-teacher">Leerkracht</span>
            @endif
            @if ($isOld)
            <span class="badge badge-old">Uitgeschreven</span>
            @endif
        </span>
    </label>
    <div class="manage-row-actions">
        <button class="btn sm" type="button" onclick="stuManageEdit(this)">Bewerk</button>
        <button class="btn sm danger" type="button"
                onclick="stuManageDelete('{{ $student->stamnummer }}', '{{ trim($student->voornaam.' '.$student->naam) ?: $student->stamnummer }}')">✕</button>
    </div>
</div>
@empty
<p style="padding:16px; color:var(--muted);">Geen leerlingen of leerkrachten gevonden.</p>
@endforelse
