# This file is part of Cash & Bank module.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import ModelView, ModelSQL, fields, Check
from trytond.pyson import Eval, Bool
from trytond.modules.log_action import LogActionMixin, write_log
from decimal import Decimal

_STATES = {
    'readonly': Bool(Eval('last_receipt')),
    }

_DEPENDS = ['last_receipt']


class DocumentType(ModelSQL, ModelView):
    "Cash/Bank Document Type"
    __name__ = "cash_bank.document.type"
    name = fields.Char('Name', required=True, translate=True)
    description = fields.Text('Description', size=None)
    active = fields.Boolean('Active')

    @staticmethod
    def default_active():
        return True


class Document(ModelSQL, ModelView):
    "Cash/Bank Document"
    __name__ = "cash_bank.document"
    type = fields.Many2One('cash_bank.document.type', 'Type',
        required=True, states=_STATES, depends=_DEPENDS)
    amount = fields.Numeric('Amount', required=True,
        states=_STATES,
        digits=(16, Eval('currency_digits', 2)),
        depends=_DEPENDS + ['currency_digits'])
    date = fields.Date('Date', states=_STATES, depends=_DEPENDS)
    party = fields.Many2One('party.party', 'Party',
        states=_STATES, depends=_DEPENDS)
    reference = fields.Char('Reference', size=None,
        states=_STATES, depends=_DEPENDS)
    entity = fields.Char('Entity', size=None,
        states=_STATES, depends=_DEPENDS)
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')
    last_receipt = fields.Many2One('cash_bank.receipt', 'Last Receipt',
        readonly=True)
    convertion = fields.Many2One('cash_bank.convertion', 'Convertion',
        readonly=True)
    logs = fields.One2Many('cash_bank.document.log_action',
        'resource', 'Logs', readonly=True)

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
        return Decimal('0.0')

    @staticmethod
    def default_currency_digits():
        return Document._get_currency_digits()

    def get_currency_digits(self, name=None):
        return Document._get_currency_digits()

    def get_rec_name(self, name):
        if self.type:
            return self.type.name
        return str(self.id)

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('type.name',) + tuple(clause[1:])]

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

        cur_receipt = None
        if hasattr(self, 'last_receipt'):
            cur_receipt = self.last_receipt

        domain = [
            ('document', '=', self.id)
            ]
        if cur_receipt:
            domain.append(
                ('receipt', '!=', cur_receipt.id)
                )

        docs = Docs.search(domain, order=[('id', 'DESC')])

        lg = 'Returned to Receipt: '
        if not docs:
            self.last_receipt = None
            lg += 'None'
        else:
            self.last_receipt = docs[0].receipt
            lg += self.last_receipt.rec_name
        write_log(lg, [self])

    @classmethod
    def create(cls, vlist):
        documents = super(Document, cls).create(vlist)
        write_log('Created', documents)
        return documents


class DocumentReceipt(ModelSQL):
    'Receipt - Document'
    __name__ = 'cash_bank.document-cash_bank.receipt'
    document = fields.Many2One('cash_bank.document', 'Document',
        ondelete='CASCADE', select=True, required=True)
    receipt = fields.Many2One('cash_bank.receipt', 'Receipt',
        ondelete='CASCADE', select=True, required=True)


class DocumentLog(LogActionMixin):
    "Document Logs"
    __name__ = "cash_bank.document.log_action"
    resource = fields.Many2One('cash_bank.document',
        'Document', ondelete='CASCADE', select=True)
