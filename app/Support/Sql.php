<?php

namespace App\Support;

use Illuminate\Support\Facades\DB;

/**
 * Kleine helpers voor SQL die zowel op MariaDB/MySQL (productie) als SQLite (tests) werkt.
 */
class Sql
{
    /** Hoofdletterongevoelige "bevat"-vergelijking: LOWER(col) LIKE %term%. */
    public static function likeExpr(string $column): string
    {
        return "LOWER({$column}) LIKE ?";
    }

    public static function likeValue(string $term): string
    {
        // Net als SQLAlchemy's ilike() zonder escaping: een % in de zoekterm werkt als wildcard.
        return '%'.mb_strtolower($term).'%';
    }

    /** Twee kolommen samenvoegen met een spatie ertussen. */
    public static function concatSpace(string $a, string $b): string
    {
        return DB::connection()->getDriverName() === 'sqlite'
            ? "({$a} || ' ' || {$b})"
            : "CONCAT({$a}, ' ', {$b})";
    }
}
