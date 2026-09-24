<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Laptop extends Model
{
    public $timestamps = false;

    protected $guarded = [];

    protected $attributes = [
        'eigen_laptop' => false,
        'is_reserve' => false,
        'hoes_ingeleverd' => true,
        'oplader_ingeleverd' => true,
    ];

    protected function casts(): array
    {
        return [
            'eigen_laptop' => 'boolean',
            'is_reserve' => 'boolean',
            'hoes_ingeleverd' => 'boolean',
            'oplader_ingeleverd' => 'boolean',
            'linked_at' => 'datetime',
            'unlinked_at' => 'datetime',
            'storage_cabinet_id' => 'integer',
        ];
    }

    public function isActive(): bool
    {
        return $this->unlinked_at === null;
    }

    public function student(): BelongsTo
    {
        return $this->belongsTo(Student::class, 'stamnummer', 'stamnummer');
    }

    public function storageCabinet(): BelongsTo
    {
        return $this->belongsTo(StorageCabinet::class);
    }
}
