<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class StorageCabinet extends Model
{
    public $timestamps = false;

    protected $guarded = [];

    protected function casts(): array
    {
        return [
            'created_at' => 'datetime',
            'capacity' => 'integer',
        ];
    }

    public function laptops(): HasMany
    {
        return $this->hasMany(Laptop::class);
    }
}
