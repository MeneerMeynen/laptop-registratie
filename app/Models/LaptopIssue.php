<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class LaptopIssue extends Model
{
    public $timestamps = false;

    protected $guarded = [];

    protected function casts(): array
    {
        return [
            'reported_date' => 'date',
            'created_at' => 'datetime',
            'reserve_laptop_id' => 'integer',
        ];
    }
}
