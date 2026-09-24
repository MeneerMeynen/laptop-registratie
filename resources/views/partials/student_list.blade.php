@forelse ($students as $student)
@php
    $laptop = $student->laptops->first(fn ($l) => $l->isActive());
    $serialDisplay = $laptop ? ($laptop->eigen_laptop ? 'Eigen laptop' : ($laptop->serial_number ?: 'Niet gekoppeld')) : 'Niet gekoppeld';
    $filterExtra = $laptop ? ($laptop->eigen_laptop ? 'eigen laptop eigen toestel' : ($laptop->serial_number ?: '')) : '';
    $isTeacher = (bool) $student->is_leerkracht;
    $groupLabel = $student->klas ?: ($student->afkorting ?: ($isTeacher ? 'Leerkracht' : ''));
    $groupLatest = $latest_import_at[$isTeacher ? 1 : 0];
    $baseFilter = ($isTeacher ? 'leerkracht ' : '').implode(' ', [
        $student->afkorting, $student->instellingsnummer, $student->naam, $student->voornaam, $student->klas,
        $student->klascode, $student->klasnummer, $student->gebruikersnaam, $student->pointer, $student->stamnummer,
    ]);
    $label = "{$student->naam}, {$student->voornaam} – {$groupLabel} ({$student->stamnummer})";
    $teacherMeta = 'Leerkracht'
        .($student->afkorting ? ' | '.$student->afkorting : '')
        .($student->gebruikersnaam ? ' | '.$student->gebruikersnaam : '');
@endphp
<button
    type="button"
    class="student-option"
    data-stamnummer="{{ $student->stamnummer }}"
    data-laptop-id="{{ $laptop ? $laptop->id : '' }}"
    data-label="{{ $label }}"
    data-base-filter="{{ $baseFilter }}"
    data-filter="{{ $baseFilter }} {{ $filterExtra }}"
    role="option"
    aria-selected="false"
    @click="selectStudent('{{ $student->stamnummer }}', '{{ $label }}')"
    @keydown.tab.prevent="document.getElementById('serial_number').focus()"
>
    <span class="student-option-name">{{ $student->naam }}, {{ $student->voornaam }}</span>
    @if ($isTeacher)
    <span class="student-option-meta">{{ $teacherMeta }}</span>
    @else
    <span class="student-option-meta">{{ $student->klascode }} | {{ $student->klas }}</span>
    @endif
    <span class="student-option-serial">Laptop serienummer: {{ $serialDisplay }}</span>
    @if ($isTeacher)
    <span class="badge badge-teacher">Leerkracht</span>
    @endif
    @if ($groupLatest && $student->last_import && $student->last_import->lt($groupLatest))
    <span class="badge badge-old">Uitgeschreven</span>
    @endif
    @if ($laptop && $laptop->eigen_laptop)
    <span class="badge badge-own">Eigen laptop</span>
    @endif
</button>
@empty
<p style="padding:16px; color:var(--muted);">Geen leerlingen of leerkrachten gevonden. Importeer eerst een CSV-bestand.</p>
@endforelse
