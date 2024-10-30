# This file is part of Cash & Bank module.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
import datetime
from decimal import Decimal
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart, get_fiscalyear
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.model.modelsql import SQLConstraintError, RequiredValidationError


class CashBankTestCase(ModuleTestCase):
    'Test CashBank module'
    module = 'cash_bank'

    @with_transaction()
    def test_cash_bank(self):
        pool = Pool()
        Account = pool.get('account.account')
        Config = pool.get('cash_bank.configuration')
        Receipt = pool.get('cash_bank.receipt')
        ReceiptLine = pool.get('cash_bank.receipt.line')
        DocumentType = pool.get('cash_bank.document.type')
        Document = pool.get('cash_bank.document')
        Docs = pool.get('cash_bank.document-cash_bank.receipt')
        Transfer = pool.get('cash_bank.transfer')
        Convertion = pool.get('cash_bank.convertion')
        CashBank = pool.get('cash_bank.cash_bank')
        ReceiptType = pool.get('cash_bank.receipt_type')

        party = self._create_party('Party test', None)
        transaction = Transaction()

        company = create_company()
        with set_company(company):
            create_chart(company)
            create_fiscalyear(company)

            account_transfer, = Account.search([
                    ('name', '=', 'Main Expense'),
                    ])
            account_cash, = Account.search([
                    ('name', '=', 'Main Cash'),
                    ])
            account_revenue, = Account.search([
                    ('name', '=', 'Main Revenue'),
                    ])
            account_expense, = Account.search([
                    ('name', '=', 'Main Expense'),
                    ])

            journal = create_journal(company, 'journal_cash')

            config = Config(
                account_transfer=account_transfer)
            config.save()

            cheque_type = DocumentType(name='Cheque')
            cheque_type.save()

            sequence = create_sequence(
                'Cash/Bank Receipt Sequence',
                'Cash and Bank Receipt',
                company)
            sequence_convertion = create_sequence(
                'Cash/Bank Convertion',
                'Cash and Bank Convertion',
                company)

            config.convertion_seq = sequence_convertion
            config.save()

            cash = create_cash_bank(
                company, 'Main Cashier', 'cash',
                journal, account_cash, sequence
                )
            self.assertEqual(len(cash.receipt_types), 2)

            _, bank_account = create_bank_account(
                party_bank=self._create_party('Party Bank', None),
                party_owner=company.party)

            with self.assertRaises(SQLConstraintError):
                # Must be a diferent account
                bank = create_cash_bank(
                    company, 'Main Bank', 'bank',
                    journal, account_cash, sequence,
                    bank_account
                    )

            with self.assertRaises(RequiredValidationError):
                # Bank Account is required for type bank
                bank = create_cash_bank(
                    company, 'Main Bank', 'bank',
                    journal, account_revenue, sequence
                    )
            ReceiptType.delete(ReceiptType.search(
                [('cash_bank.type', '=', 'bank')]))
            CashBank.delete(CashBank.search(
                [('type', '=', 'bank')]))

            bank = create_cash_bank(
                company, 'Main Bank', 'bank',
                journal, account_revenue, sequence,
                bank_account
                )
            self.assertEqual(len(bank.receipt_types), 2)

            date = datetime.date.today()

            # Receipt Cash IN
            receipt = create_receipt(
                company, cash, 'in', date)

            receipt.cash = Decimal('100.0')
            receipt.save()

            self.assertEqual(receipt.state, 'draft')
            self.assertEqual(receipt.diff, Decimal('-100.0'))

            line = ReceiptLine(
                receipt=receipt,
                amount=Decimal('100.0'),
                account=account_revenue,
                type='move_line',
                )
            
            receipt.lines = [line]
            receipt.save()

            self.assertEqual(len(receipt.lines), 1)
            self.assertEqual(receipt.diff, Decimal('0.0'))
            self.assertEqual(receipt.state, 'draft')
            self.assertEqual(receipt.move, None)

            Receipt.confirm([receipt])
            self.assertEqual(receipt.state, 'confirmed')
            self.assertEqual(receipt.move.state, 'draft')

            Receipt.cancel([receipt])
            self.assertEqual(receipt.state, 'cancel')
            self.assertEqual(receipt.move, None)

            Receipt.draft([receipt])
            self.assertEqual(receipt.state, 'draft')
            self.assertEqual(receipt.move, None)

            Receipt.confirm([receipt])
            self.assertEqual(receipt.state, 'confirmed')
            self.assertEqual(receipt.move.state, 'draft')

            Receipt.post([receipt])
            self.assertEqual(receipt.state, 'posted')
            self.assertEqual(receipt.move.state, 'posted')

            # Nothing change because 'posted' to 'cancel'
            # not in cls._transitions
            Receipt.cancel([receipt])
            self.assertEqual(receipt.state, 'posted')
            self.assertEqual(receipt.move.state, 'posted')

            # Receipt Cash OUT
            receipt = create_receipt(
                company, cash, 'out', date, party)

            receipt.cash = Decimal('100.0')
            receipt.save()

            line = ReceiptLine(
                receipt=receipt,
                amount=Decimal('100.0'),
                account=account_expense,
                type='move_line'
                )

            receipt.lines = [line]
            receipt.save()

            Receipt.confirm([receipt])
            Receipt.post([receipt])

            # 'out' receipts can not create documents
            receipt = create_receipt(
                company, cash, 'out', date)
            receipt.cash = Decimal('10.0')
            receipt.save()
            with self.assertRaises(UserError):
                docs = [
                    self._get_document(
                        cheque_type, Decimal('20.0'), date, 'a'),
                    self._get_document(
                        cheque_type, Decimal('30.0'), date, 'b'),
                    self._get_document(
                        cheque_type, Decimal('40.0'), date, 'c'),
                    ]
                receipt.documents = docs
                receipt.save()
            Receipt.delete([receipt])
            Document.delete(Document.search([]))

            # Receipt IN with cash and documents

            receipt = create_receipt(
                company, cash, 'in', date)
            receipt.cash = Decimal('10.0')

            docs = [
                self._get_document(
                    cheque_type, Decimal('20.0'), date, 'abc'),
                self._get_document(
                    cheque_type, Decimal('30.0'), date, 'def'),
                self._get_document(
                    cheque_type, Decimal('40.0'), date, 'ghi'),
                ]
            receipt.documents = docs
            receipt.save()

            self.assertEqual(len(receipt.documents), 3)
            self.assertEqual(receipt.total_documents, Decimal('90.0'))
            self.assertEqual(receipt.total, Decimal('100.0'))
            self.assertEqual(receipt.diff, Decimal('-100.0'))

            self._verify_document('abc', receipt.id)
            self._verify_document('def', receipt.id)
            self._verify_document('ghi', receipt.id)

            line = ReceiptLine(
                receipt=receipt,
                amount=Decimal('100.0'),
                account=account_revenue,
                type='move_line',
                )
            receipt.lines = [line]
            receipt.save()

            Receipt.confirm([receipt])

            with self.assertRaises(UserError):
                # Should be 'draft' state
                Receipt.delete([receipt])

            Receipt.cancel([receipt])
            Receipt.draft([receipt])
            Receipt.delete([receipt])

            docs = Docs.search([])  # cash_bank.document-cash_bank.receipt
            self.assertEqual(len(docs), 0)

            docs = Document.search([])  # cash_bank.document
            self.assertEqual(len(docs), 3)
            self._verify_document('abc', None)
            self._verify_document('def', None)
            self._verify_document('ghi', None)

            ########################
            # Documents domain tests
            ########################

            receipt_1 = create_receipt(
                company, cash, 'in', date)
            receipt_1.cash = Decimal('10.0')
            receipt_1.lines = [
                ReceiptLine(
                    amount=Decimal('100.0'),
                    account=account_expense,
                    type='move_line'
                )]
            receipt_1.documents = Document.search([])
            receipt_1.save()
            self._verify_document('abc', receipt_1.id)
            self._verify_document('def', receipt_1.id)
            self._verify_document('ghi', receipt_1.id)

            # if documents are detached then returns to a previous receipt
            receipt_1.documents = [Document.search([])[0]]
            receipt_1.save()
            self._verify_document('abc', receipt_1.id)
            self._verify_document('def', None)
            self._verify_document('ghi', None)
            Receipt.delete([receipt_1])

            # Ensure that if docs belongs to a receipt 'in'
            # no other receipt 'in' can add them
            receipt_1 = create_receipt(
                company, cash, 'in', date)
            receipt_1.cash = Decimal('10.0')
            receipt_1.lines = [
                ReceiptLine(
                    amount=Decimal('100.0'),
                    account=account_expense,
                    type='move_line'
                )]
            receipt_1.documents = Document.search([])
            receipt_1.save()
            self._validate_domain_in(Receipt, Document, receipt_1)

            # Same if receipt_1 is confirmed
            Receipt.confirm([receipt_1])
            self._validate_domain_in(Receipt, Document, receipt_1)

            # Same if receipt_1 is canceled
            Receipt.cancel([receipt_1])
            self.assertEqual(receipt_1.state, 'cancel')
            self.assertEqual(receipt_1.move, None)
            self._validate_domain_in(Receipt, Document, receipt_1)

            # Same if receipt_1 is draft
            Receipt.draft([receipt_1])
            self._validate_domain_in(Receipt, Document, receipt_1)

            # Same if receipt_1 is confirmed
            Receipt.confirm([receipt_1])
            self._validate_domain_in(Receipt, Document, receipt_1)

            # Same if receipt_1 is posted
            Receipt.post([receipt_1])
            self.assertEqual(receipt_1.state, 'posted')
            self.assertEqual(receipt_1.move.state, 'posted')
            self._validate_domain_in(Receipt, Document, receipt_1)

            last_docs_receipt_id = receipt_1.id

            # Group of Receipts
            receipt_grp_1 = create_receipt(
                company, cash, 'in', date)
            receipt_grp_1.cash = Decimal('10.0')
            receipt_grp_2 = create_receipt(
                company, cash, 'in', date)
            receipt_grp_2.cash = Decimal('20.0')

            Receipt.save([receipt_grp_1, receipt_grp_2])
            self.assertEqual(receipt_grp_1.cash, Decimal('10.0'))
            self.assertEqual(receipt_grp_2.cash, Decimal('20.0'))

            receipt_grp_1.cash = Decimal('15.0')
            receipt_grp_2.cash = Decimal('25.0')

            Receipt.save([receipt_grp_1, receipt_grp_2])
            self.assertEqual(receipt_grp_1.cash, Decimal('15.0'))
            self.assertEqual(receipt_grp_2.cash, Decimal('25.0'))

            #####################################
            # Transfer (specially with documents)
            #####################################

            cash_2 = create_cash_bank(
                company, 'Cashier 2', 'cash',
                journal, account_expense, sequence
                )

            with self.assertRaises(UserError):
                # Raise document domain error because
                # documents are not in cash_2
                transfer = Transfer(
                    company=company,
                    date=date,
                    cash_bank_from=cash_2,
                    type_from=cash_2.receipt_types[1],  # out
                    cash_bank_to=cash,
                    type_to=cash.receipt_types[0],  # in
                    documents=Document.search([])
                    )
                transfer.save()

            transfer = Transfer(
                company=company,
                date=date,
                cash=Decimal('10.0'),
                cash_bank_from=cash,
                type_from=cash.receipt_types[1],  # out
                cash_bank_to=cash_2,
                type_to=cash_2.receipt_types[0],  # in
                documents=Document.search([])
                )
            transfer.save()
            self.assertEqual(transfer.total_documents, Decimal('90.0'))
            self.assertEqual(transfer.total, Decimal('100.0'))
            self.assertEqual(transfer.state, 'draft')
            self.assertEqual(transfer.receipt_from, None)
            self.assertEqual(transfer.receipt_to, None)

            Transfer.confirm([transfer])
            self.assertEqual(transfer.state, 'confirmed')
            self.assertEqual(transfer.receipt_from.transfer, transfer)
            self.assertEqual(transfer.receipt_to.transfer, transfer)
            self.assertEqual(transfer.receipt_from.state, 'confirmed')
            self.assertEqual(transfer.receipt_to.state, 'confirmed')

            self._verify_document('abc', transfer.receipt_to.id)
            self._verify_document('def', transfer.receipt_to.id)
            self._verify_document('ghi', transfer.receipt_to.id)

            Transfer.cancel([transfer])
            self.assertEqual(transfer.state, 'cancel')
            self.assertEqual(transfer.receipt_from.transfer, transfer)
            self.assertEqual(transfer.receipt_to.transfer, transfer)
            self.assertEqual(transfer.receipt_from.state, 'cancel')
            self.assertEqual(transfer.receipt_to.state, 'cancel')

            self._verify_document('abc', transfer.receipt_to.id)
            self._verify_document('def', transfer.receipt_to.id)
            self._verify_document('ghi', transfer.receipt_to.id)

            Transfer.draft([transfer])
            self.assertEqual(transfer.state, 'draft')
            self.assertEqual(transfer.receipt_from, None)
            self.assertEqual(transfer.receipt_to, None)

            # Documents go back to the origin receipt
            self._verify_document('abc', last_docs_receipt_id)
            self._verify_document('def', last_docs_receipt_id)
            self._verify_document('ghi', last_docs_receipt_id)

            Transfer.confirm([transfer])
            self.assertEqual(transfer.state, 'confirmed')
            self.assertEqual(transfer.receipt_from.transfer, transfer)
            self.assertEqual(transfer.receipt_to.transfer, transfer)
            self.assertEqual(transfer.receipt_from.state, 'confirmed')
            self.assertEqual(transfer.receipt_to.state, 'confirmed')

            self._verify_document('abc', transfer.receipt_to.id)
            self._verify_document('def', transfer.receipt_to.id)
            self._verify_document('ghi', transfer.receipt_to.id)

            Transfer.post([transfer])
            self.assertEqual(transfer.state, 'posted')
            self.assertEqual(transfer.receipt_from.transfer, transfer)
            self.assertEqual(transfer.receipt_to.transfer, transfer)
            self.assertEqual(transfer.receipt_from.state, 'posted')
            self.assertEqual(transfer.receipt_to.state, 'posted')

            self._verify_document('abc', transfer.receipt_to.id)
            self._verify_document('def', transfer.receipt_to.id)
            self._verify_document('ghi', transfer.receipt_to.id)

            # Convertions

            with self.assertRaises(UserError):
                # Documents are in cash_2
                convertion = Convertion(
                    cash_bank=cash,
                    date=date,
                    documents=Document.search([])
                    )
                convertion.save()

            convertion = Convertion(
                cash_bank=cash_2,
                date=date,
                documents=Document.search([])
                )
            convertion.save()

            Convertion.confirm([convertion])
            self.assertEqual(convertion.state, 'confirmed')
            docs = Document.search([])
            for doc in docs:
                self.assertEqual(doc.convertion.id, convertion.id)

            Convertion.cancel([convertion])
            self.assertEqual(convertion.state, 'cancel')
            docs = Document.search([])
            for doc in docs:
                self.assertEqual(doc.convertion.id, convertion.id)

            Convertion.draft([convertion])
            self.assertEqual(convertion.state, 'draft')
            docs = Document.search([])
            for doc in docs:
                self.assertEqual(doc.convertion, None)

    def _validate_domain_in(self, Receipt, Document, receipt_1):
        self._verify_document('abc', receipt_1.id)
        self._verify_document('def', receipt_1.id)
        self._verify_document('ghi', receipt_1.id)

        receipt_2 = create_receipt(
            receipt_1.company, receipt_1.cash_bank, 'in', receipt_1.date)
        receipt_2.cash = Decimal('10.0')
        receipt_2.save()
        with self.assertRaises(UserError):
            receipt_2.documents = Document.search([])
            receipt_2.save()
        receipt_2.documents = None
        receipt_2.save()
        Receipt.delete([receipt_2])

        # Verify docs again
        self._verify_document('abc', receipt_1.id)
        self._verify_document('def', receipt_1.id)
        self._verify_document('ghi', receipt_1.id)

    def _verify_document(self, reference, receipt_id):
        pool = Pool()
        Document = pool.get('cash_bank.document')
        Docs = pool.get('cash_bank.document-cash_bank.receipt')

        doc = Document.search([
            ('reference', '=', reference)
            ])[0]

        docs = Docs.search(
            [('document', '=', doc.id)], order=[('id', 'ASC')])

        if receipt_id is None:
            self.assertEqual(doc.last_receipt, receipt_id)
            self.assertEqual(docs, [])
        else:
            self.assertEqual(doc.last_receipt.id, receipt_id)
            self.assertEqual(receipt_id, docs[-1].receipt.id)

    def _get_document(self, type_, amount, date, reference):
        Document = Pool().get('cash_bank.document')
        doc = Document(
            type=type_,
            amount=amount,
            date=date,
            reference=reference
            )
        return doc

    @classmethod
    def _create_party(cls, name, account):
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        addr = Address(
            name=name,
            )
        party = Party(
            name=name,
            account_receivable=account,
            addresses=[addr],
            )
        party.save()
        return party


def create_bank_account(party_bank, party_owner):
    pool = Pool()
    Bank = pool.get('bank')
    Account = pool.get('bank.account')
    Number = pool.get('bank.account.number')
    PartyAccount = pool.get('bank.account-party.party')

    bank = Bank(
        party=party_bank,
        )
    bank.save()

    account = Account(
        bank=bank,
        numbers=[Number(
            type='other',
            number='12345678'
            )]
        )
    account.save()

    party_account = PartyAccount(
        owner=party_owner,
        account=account
        )
    party_account.save()

    return bank, account


def create_fiscalyear(company):
    pool = Pool()
    FiscalYear = pool.get('account.fiscalyear')
    InvoiceSequence = pool.get(
        'account.fiscalyear.invoice_sequence')

    invoice_seq = create_sequence(
        'Invoice Sequence', 'Invoice', company.id, True)

    seq = InvoiceSequence()
    seq.company = company
    seq.out_invoice_sequence = invoice_seq
    seq.out_credit_note_sequence = invoice_seq
    seq.in_invoice_sequence = invoice_seq
    seq.in_credit_note_sequence = invoice_seq

    fy = get_fiscalyear(company)
    fy.invoice_sequences = [seq]
    fy.save()
    FiscalYear.create_period([fy])


def create_journal(company, fs_id):
    pool = Pool()
    ModelData = pool.get('ir.model.data')
    Journal = pool.get('account.journal')
    journal = Journal(ModelData.get_id('account', fs_id))
    return journal


def create_receipt_types(name, sequence):
    pool = Pool()
    ReceiptType = pool.get('cash_bank.receipt_type')
    types = ['in', 'out']

    res = []
    for t in types:
        rt = ReceiptType(
            name=name + ' ' + t,
            type=t,
            sequence=sequence,
            default_receipt_line_type='move_line'
        )
        res.append(rt)
    return res


def create_sequence(name, type_, company, is_strict=False):
    pool = Pool()
    Type_ = pool.get('ir.sequence.type')
    if is_strict:
        Sequence = pool.get('ir.sequence.strict')
    else:
        Sequence = pool.get('ir.sequence')
    seq = Sequence(
        name=name,
        sequence_type=Type_.search([('name', '=', type_)])[0],
        company=company,
        type='incremental'
        )
    seq.save()
    return seq


def create_cash_bank(
        company, name, type_, journal, account,
        receipt_sequence, bank_account=None):
    CashBank = Pool().get('cash_bank.cash_bank')

    cash = CashBank(
        company=company,
        name=name,
        type=type_,
        journal_cash_bank=journal,
        account=account,
        bank_account=bank_account,
        receipt_types=create_receipt_types(name, receipt_sequence)
        )
    cash.save()
    return cash


def create_receipt(
        company, cash_bank, receipt_type, date, party=None):
    pool = Pool()
    Receipt = pool.get('cash_bank.receipt')
    ReceiptType = pool.get('cash_bank.receipt_type')

    type_ = ReceiptType.search([
        ('cash_bank', '=', cash_bank.id),
        ('type', '=', receipt_type)])[0]

    receipt = Receipt(
        company=company,
        cash_bank=cash_bank,
        type=type_,
        date=date,
        party=party,
        )
    return receipt


del ModuleTestCase
