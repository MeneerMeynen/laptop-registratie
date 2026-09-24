<?php

namespace App\Support;

use DateTimeInterface;

/**
 * Formatteringshelpers die de uitvoer van de Python-versie nabootsen.
 */
class Fmt
{
    /** ISO-datum-tijd zonder tijdzone (zoals Pydantic), bv. 2026-09-24T10:15:00. */
    public static function iso(?DateTimeInterface $value): ?string
    {
        return $value?->format('Y-m-d\TH:i:s');
    }

    /** ISO-datum, bv. 2026-09-24. */
    public static function date(?DateTimeInterface $value): ?string
    {
        return $value?->format('Y-m-d');
    }

    /** Equivalent van strftime('%-d %b %Y'), bv. "4 Sep 2026". */
    public static function short(?DateTimeInterface $value): string
    {
        return $value ? $value->format('j M Y') : '';
    }

    /** Neutraliseer formule-injectie in spreadsheets (cellen die met =, +, - of @ beginnen). */
    public static function csvSafe(?string $value): string
    {
        if ($value === null || $value === '') {
            return '';
        }

        return str_contains('=+-@', $value[0]) ? "'".$value : $value;
    }

    /** Waarde als boolean interpreteren zoals FastAPI (true/1/yes/on). */
    public static function bool(mixed $value, bool $default = false): bool
    {
        if ($value === null || $value === '') {
            return $default;
        }

        return filter_var($value, FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE) ?? $default;
    }

    /** Getrimde string of null als leeg (Python: (x or '').strip() or None). */
    public static function strOrNull(mixed $value): ?string
    {
        $trimmed = trim((string) ($value ?? ''));

        return $trimmed === '' ? null : $trimmed;
    }
}
