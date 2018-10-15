# This file is part of trytond-cash_bank module.
# The COPYRIGHT file at the top level of this repository
# contains the full copyright notices and license terms.

from trytond.pool import Pool
from .configuration import *
from .account import *
from .cash_bank import *
from .document import *
from .receipt import *
from .transfer import *
from .convertion import *


def register():
    Pool.register(
        Configuration,
        ConfigurationAccount,
        Move,
        CashBank,
        ReceiptType,
        DocumentType,
        Document,
        DocumentReceipt,
        Receipt,
        Line,
        Transfer,
        Convertion,
        module='cash_bank', type_='model')
