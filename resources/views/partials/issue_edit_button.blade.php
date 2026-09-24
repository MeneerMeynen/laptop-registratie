<button type="button" class="lt-icon-btn lt-icon-btn-edit"
    title="Bewerken"
    data-issue-id="{{ $issue['id'] }}"
    data-serial="{{ $issue['serial_number'] }}"
    data-description="{{ $issue['description'] }}"
    data-date="{{ $issue['reported_date']?->format('Y-m-d') }}"
    data-status="{{ $issue['status'] }}"
    data-category="{{ $issue['category'] ?? '' }}"
    data-solution="{{ $issue['solution'] ?? '' }}"
    data-reserve-laptop-id="{{ $issue['reserve_laptop_id'] ?: '' }}"
    @click="startEditIssue($el.dataset)">
    <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="overflow:visible"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
</button>
