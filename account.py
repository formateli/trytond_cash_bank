# This file is part of Cash & Bank module.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields

class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        return super(Move, cls)._get_origin() + ['cash_bank.receipt']


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'
    cash_bank_receipt_line = fields.One2Many('cash_bank.receipt.line',
        'line_move', 'Receipt Line', readonly=True)
