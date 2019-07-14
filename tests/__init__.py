# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.cash_bank.tests.test_cash_bank import (
        suite, create_cash_bank, create_sequence,
        create_payment_method, create_fiscalyear)
except ImportError:
    from .test_cash_bank import (
        suite, create_cash_bank, create_sequence,
        create_payment_method, create_fiscalyear)

__all__ = ['suite']