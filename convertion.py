# This file is part of Cash & Bank module.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.pyson import Eval, If, Or
from trytond.modules.log_action import LogActionMixin, write_log
from trytond.i18n import gettext
from trytond.exceptions import UserError
from decimal import Decimal

_STATES = {
    'readonly': Eval('state') != 'draft',
}

_DEPENDS = ['state']

STATES = [
    ('draft', 'Draft'),
    ('confirmed', 'Confirmed'),
    ('cancel', 'Canceled'),
    ]


class Convertion(Workflow, ModelSQL, ModelView):
    "Cash/Bank Convert Documents to Cash"
    __name__ = "cash_bank.convertion"
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': True,
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    number = fields.Char('Number', size=None, readonly=True)
    cash_bank = fields.Many2One('cash_bank.cash_bank',
        'Cash', required=True,
        domain=[
            ('company', '=', Eval('company')),
            ('type', '=', 'cash'),
            ],
        states={
            'readonly': Or(Eval('state') != 'draft', Eval('documents')),
            },
        depends=_DEPENDS + ['company', 'documents'])
    date = fields.Date('Date', required=True,
        states=_STATES, depends=_DEPENDS)
    description = fields.Char('Description', size=None)
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': True,
            },
        depends=['state', 'documents'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    documents = fields.Many2Many('cash_bank.document-cash_bank.convertion',
        'convertion', 'document', 'Documents',
        domain=[
            ('last_receipt', '!=', None),
            ('last_receipt.cash_bank.id', '=', Eval('cash_bank', -999)),
            If(Eval('state') == 'draft',
                [
                    ('convertion', '=', None),
                ],
                [
                    ('convertion', '!=', None),
                    ('convertion.id', '=', Eval('id', -999)),
                ]
            )
        ],
        states=_STATES,
        depends=_DEPENDS + ['cash_bank', 'id'])
    total_documents = fields.Function(fields.Numeric('Total Documents',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
            'get_total_documents')
    state = fields.Selection(STATES, 'State', readonly=True, required=True)
    logs = fields.One2Many('cash_bank.convertion.log_action',
        'resource', 'Logs', readonly=True)

    @classmethod
    def __setup__(cls):
        super(Convertion, cls).__setup__()
        cls._order[0] = ('id', 'DESC')

        cls._transitions |= set(
            (
                ('draft', 'confirmed'),
                ('confirmed', 'cancel'),
                ('cancel', 'draft'),
            )
            )

        cls._buttons.update({
            'cancel': {
                'invisible': ~Eval('state').in_(['confirmed']),
                },
            'confirm': {
                'invisible': ~Eval('state').in_(['draft']),
                },
            'draft': {
                'invisible': ~Eval('state').in_(['cancel']),
                'icon': If(
                    Eval('state') == 'cancel',
                    'tryton-clear', 'tryton-go-previous'),
                },
            })

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_total_documents():
        return Decimal('0.0')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.id

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.digits
        return 2

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @fields.depends('documents')
    def on_change_documents(self):
        self.total_documents = self.get_total_documents()

    def get_total_documents(self, name=None):
        total = Decimal('0.0')
        if self.documents:
            for doc in self.documents:
                if doc.amount:
                    total += doc.amount
        return total

    def get_rec_name(self, name):
        if self.number:
            return self.number
        return str(self.id)

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('number',) + tuple(clause[1:])]

    @classmethod
    def set_number(cls, convertions):
        pool = Pool()
        Config = pool.get('cash_bank.configuration')
        config = Config(1)
        for convertion in convertions:
            if convertion.number:
                continue
            convertion.number = config.get_multivalue(
                'convertion_seq', company=convertion.company.id).get()
        cls.save(convertions)

    @classmethod
    def create(cls, vlist):
        convertions = super(Convertion, cls).create(vlist)
        write_log('Created', convertions)
        return convertions

    @classmethod
    def delete(cls, convertions):
        Document = Pool().get('cash_bank.document')
        docs = []
        for convertion in convertions:
            if convertion.state != 'draft':
                raise UserError(
                    gettext('cash_bank.msg_delete_document_cash_bank',
                        doc_name='Convertion',
                        doc_number=convertion.rec_name,
                        state='Draft'
                    ))
            for doc in convertion.documents:
                doc.convertion = None
                docs.append(doc)
                write_log(
                    'Convertion ' + convertion.rec_name + ' deleted.',
                    [doc])
        Document.save(docs)
        super(Convertion, cls).delete(convertions)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, convertions):
        Document = Pool().get('cash_bank.document')
        docs = []
        for convertion in convertions:
            for doc in convertion.documents:
                doc.convertion = None
                docs.append(doc)
                write_log(
                    'Convertion ' + convertion.rec_name + ' to Draft.',
                    [doc])
        Document.save(docs)
        write_log('Draft', convertions)

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, convertions):
        Document = Pool().get('cash_bank.document')
        docs = []
        for convertion in convertions:
            for doc in convertion.documents:
                doc.convertion = convertion
                write_log(
                    'Convertion ' + convertion.rec_name + ' confirmed.',
                    [doc])
                docs.append(doc)
        Document.save(docs)
        cls.set_number(convertions)
        write_log('Confirmed', convertions)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, convertions):
        write_log('Cancelled', convertions)


class DocumentConvertion(ModelSQL):
    'Convertion - Document'
    __name__ = 'cash_bank.document-cash_bank.convertion'
    document = fields.Many2One('cash_bank.document', 'Document',
        ondelete='CASCADE', required=True)
    convertion = fields.Many2One('cash_bank.convertion', 'Convertion',
        ondelete='CASCADE', required=True)


class ConvertionLog(LogActionMixin):
    "Convertion Logs"
    __name__ = "cash_bank.convertion.log_action"
    resource = fields.Many2One('cash_bank.convertion',
        'Receipt', ondelete='CASCADE')
