# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import configuration
from . import account
from . import cash_bank
from . import document
from . import receipt
from . import transfer
from . import convertion
from . import party


def register():
    Pool.register(
        configuration.Configuration,
        configuration.ConfigurationAccount,
        configuration.ConfigurationSequences,
        configuration.ConfigurationOther,
        account.Move,
        cash_bank.CashBank,
        cash_bank.ReceiptType,
        document.DocumentType,
        document.Document,
        document.DocumentReceipt,
        document.DocumentLog,
        receipt.ReceiptLog,
        receipt.Receipt,
        receipt.Line,
        transfer.Transfer,
        transfer.DocumentTransfer,
        transfer.TransferLog,
        convertion.Convertion,
        convertion.DocumentConvertion,
        convertion.ConvertionLog,
        module='cash_bank', type_='model')
    Pool.register(
        party.PartyReplace,
        module='cash_bank', type_='wizard')
