Cash & Bank Module
##################

Manages money flow through receipts (AKA Vouchers), and
generates corresponding account entries.

This module allow to pay Invoices for one or multiples parties
in one single Receipt.


Configuration
*************

Defines the module configuration.

- Account Transfer: Account used as transit account when transfers
  between Cash/Bank take place.


Cash & Bank
***********

Defines a Cash/Bank.

- Name: Cash/Bank name (Ex: Bank of Panama, Main cashier, etc).
- Company: Company for wich this Cash/Bank is defined.
- Type: The Cash/Bank type ('Cash' or 'Bank').
- Payment Method: Account Payment Method defined for the Cash/Bank.
- Receipt types: Receipts types defined for the Cash/Bank.


Receipt Type
************

Defines a receipt type for a Cash/Bank. Usually just two receipt type are needed,
one for incomes and other for outcomes, but multiple receipt type can be
configured.

- Cash/Bank = The Cash/Bank for wich receipt type is defined.
- Name: The name of the receipt type (Ex: Cheque, Income, Direct debit, etc).
- Type: Type of receipt. ('IN' or 'OUT').
- Sequence: Sequence used for receipt enumeration.
- Convert documents: Automatically convert documents to cash.
- Party Required: A party is required by this receipt type.


Document Type
*************

Defines the type of documents than can be managed besides cash.

- Name: The name of document type (Ex: Cheque, Promise of pay, etc)
- Description: A description of the document type.


Document
********

Document created in a 'IN' type receipt.
Documents can be transfered between Cash/Bank's or can be
converted to cash as well.

- Type: Document type.
- Amount: Document amount.
- Date: Document date.
- Reference: Document reference. Usally the number of the physical document.
- Entity: Document entity. (Ex Bank name in case of cheque).


Receipt
*******

A Receipt that defines money movement.

- Company: Receipt company.
- Cash/Bank: Receipt Cash/Bank.
- Type: Receipt type.
- Number: Recipt number.
- Reference: Receipt reference.
- Description: Receipt description.
- Date: Recipt date.
- Party: Reciept party.
- Cash: Cash amount.
- Documents: Documents associated to the Receipt.
- Lines: Lines of the Receipt
- Account Move Line: Account entry created for the receipt according to Cash/Bank journal.
- State: Receipt state.


Receipt Line
************

Line defined for a Receipt.
Each line must be associated with an account.

- Number: Line number.
- Amount: Line amount.
- Party: Line party.
- Account: Line Account.
- Description: Line description.
- Invoice: Invoice associated with line.
- Line move: Account move line (once receipt is posted).


Transfer
********

A transfer between two Cash/Bank.
Two Receipts are created automatically for each transfer.
It can involves cash and/or documents.

- Company: Transfer company.
- Date: Transfer date.
- Reference: TRansfer reference.
- Description: Transfer description.
- From: Origin Cash/Bank.
- Type: Origin receipt type.
- To: Destination Cash/Bank.
- Type: Destination receipt type.
- Party: Transfer party.
- Cash: Cash amount.
- Documents: Documents associated to the transfer.
- Receipt from: The origin Receipt.
- Receipt to: The destination Receipt.
