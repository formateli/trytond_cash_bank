# This file is part of trytond-cash_bank module.
# The COPYRIGHT file at the top level of this repository
# contains the full copyright notices and license terms.

from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import ModelView, ModelSQL, fields, Check
from trytond.pyson import Eval, If, Bool
from decimal import Decimal

__all__ = ['DocumentType', 'Document', 'DocumentReceipt']

_STATES = {
    'readonly': If(Bool(Eval('last_receipt')), True, False),
    }


class DocumentType(ModelSQL, ModelView):
    "Cash/Bank Document Type"
    __name__ = "cash_bank.document.type"
    name = fields.Char('Name', required=True, translate=True)
    active = fields.Boolean('Active')
    description = fields.Text('Description', size=None)

    @staticmethod
    def default_active():
        return True


class Document(ModelSQL, ModelView):
    "Cash/Bank Document"
    __name__ = "cash_bank.document"
    #_rec_name = 'type.name'
    type = fields.Many2One('cash_bank.document.type', 'Type',
        required=True,
        states=_STATES)
    amount = fields.Numeric('Amount', required=True,
        states=_STATES,
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    date = fields.Date('Date', states=_STATES)
    reference = fields.Char('Reference', size=None,
        states=_STATES)
    entity = fields.Char('Entity', size=None,
        states=_STATES)
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')
    last_receipt = fields.Many2One('cash_bank.receipt', 'Last Receipt',
        readonly=True)
    convertion = fields.Many2One('cash_bank.convertion', 'Convertion',
        readonly=True)

    @classmethod
    def __setup__(cls):
        super(Document, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('check_receipt_doc_amount', Check(t, t.amount > 0),
                'Amount must be greater than zero.'),
            ]

    @staticmethod
    def default_amount():
        return Decimal(0)

    @staticmethod
    def default_currency_digits():
        return Document._get_currency_digits()

    def get_currency_digits(self, name=None):
        return Document._get_currency_digits()

    @staticmethod
    def _get_currency_digits():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.digits
        return 2

    def set_previous_receipt(self):
        Docs = Pool().get('cash_bank.document-cash_bank.receipt')
        docs = Docs.search(
            [('document', '=', self.id)], order=[('id', 'ASC')])
        if not docs:
            self.last_receipt = None
        else:
            self.last_receipt = docs[-1].receipt


class DocumentReceipt(ModelSQL):
    'Receipt - Document'
    __name__ = 'cash_bank.document-cash_bank.receipt'
    document = fields.Many2One('cash_bank.document', 'Document',
        ondelete='CASCADE', select=True, required=True)
    receipt = fields.Many2One('cash_bank.receipt', 'Receipt',
        ondelete='CASCADE', select=True, required=True)
