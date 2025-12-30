# -*- coding: utf-8 -*-
# © 2023 Tiago Prates <tiago.prates@allss.com.br>, ALLSS Soluções em Sistemas LTDA
# import logging
# _logger = logging.getLogger(__name__)

from odoo import fields, models, api


class L10nBrAllssAccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_br_allss_import_nfe_tax = fields.Text('Impostos da NF-e Importada')

    @api.model
    def _get_fields_onchange_balance_model(
            self, quantity, discount, amount_currency, move_type, currency, taxes, price_subtotal,
            force_computation=False):
        ''' This method is used to recompute the values of 'quantity', 'discount', 'price_unit'
        due to a change made in some accounting fields such as 'balance'.

        This method is a bit complex as we need to handle some special cases.
        For example, setting a positive balance with a 100% discount.

        :param quantity:        The current quantity.
        :param discount:        The current discount.
        :param amount_currency: The new balance in line's currency.
        :param move_type:       The type of the move.
        :param currency:        The currency.
        :param taxes:           The applied taxes.
        :param price_subtotal:  The price_subtotal.
        :return:                A dictionary containing 'quantity', 'discount', 'price_unit'.
        '''
        if move_type in self.move_id.get_outbound_types():
            sign = 1
        elif move_type in self.move_id.get_inbound_types():
            sign = -1
        else:
            sign = 1
        amount_currency *= sign

        # Avoid rounding issue when dealing with price included taxes. For example, when the
        # price_unit is 2300.0 and
        # a 5.5% price included tax is applied on it, a balance of 2300.0 / 1.055 = 2180.094 ~
        # 2180.09 is computed.
        # However, when triggering the inverse, 2180.09 + (2180.09 * 0.055) = 2180.09 + 119.90 =
        # 2299.99 is computed.
        # To avoid that, set the price_subtotal at the balance if the difference between them looks
        # like a rounding issue.
        if not force_computation and currency.is_zero(amount_currency - price_subtotal):
            return {}

        taxes = taxes.flatten_taxes_hierarchy()
        if taxes and any(tax.price_include_override == 'tax_included' for tax in taxes):
            # Inverse taxes. E.g:
            #
            # Price Unit    | Taxes         | Originator Tax    |Price Subtotal     | Price Total
            # -----------------------------------------------------------------------------------
            # 110           | 10% incl, 5%  |                   | 100               | 115
            # 10            |               | 10% incl          | 10                | 10
            # 5             |               | 5%                | 5                 | 5
            #
            # When setting the balance to -200, the expected result is:
            #
            # Price Unit    | Taxes         | Originator Tax    |Price Subtotal     | Price Total
            # -----------------------------------------------------------------------------------
            # 220           | 10% incl, 5%  |                   | 200               | 230
            # 20            |               | 10% incl          | 20                | 20
            # 10            |               | 5%                | 10                | 10
            force_sign = -1 if move_type in ('out_invoice', 'in_refund', 'out_receipt') else 1
            allss_calculation_base = 0
            if self.env.context.get('allss_nfe_import', False) and 'l10n_br_allss_import_nfe_tax' in \
                    self._fields:
                import_nfe_tax_data = self.l10n_br_allss_import_nfe_tax or self.env.context.get(
                    'allss_nfe_import_tax_data', False)
                if import_nfe_tax_data:
                    for tax in taxes:
                        import_tax_data = eval(import_nfe_tax_data).get(
                            tax.l10n_br_allss_account_tax_id.l10n_br_allss_tax_registration_id.
                            l10n_br_allss_code.lower(), {}) or {}
                        # _logger.warning(f'>>>>>>>>>> ALLSS > _get_fields_onchange_balance_model > import_tax_data ({type(import_tax_data)}): {import_tax_data}')
                        if import_tax_data and type(import_tax_data) == dict:
                            allss_calculation_base = import_tax_data.get('base_calculo', 0) or 0
                            amount_currency += (import_tax_data.get('valor', 0) or 0)
                        else:
                            allss_calculation_base = 0
            if not allss_calculation_base:
                taxes_res = taxes._origin.with_context(force_sign=force_sign).compute_all(
                    amount_currency, currency=currency, handle_price_include=False)
                for tax_res in taxes_res.get('taxes', {}):
                    tax = self.env.get('account.tax').sudo().browse(tax_res.get('id', False))
                    if tax.price_include_override == 'tax_included':
                        amount_currency += tax_res.get('amount', 0)

        discount_factor = 1 - (discount / 100.0)
        if amount_currency and discount_factor:
            # discount != 100%
            vals = {
                'quantity': quantity or 1.0,
                'price_unit': amount_currency / discount_factor / (quantity or 1.0),
            }
        elif amount_currency and not discount_factor:
            # discount == 100%
            vals = {
                'quantity': quantity or 1.0,
                'discount': 0.0,
                'price_unit': amount_currency / (quantity or 1.0),
            }
        elif not discount_factor:
            # balance of line is 0, but discount  == 100% so we display the normal unit_price
            vals = {}
        else:
            # balance is 0, so unit price is 0 as well
            vals = {'price_unit': 0.0}
        return vals

    def _get_price_total_and_subtotal(
            self, price_unit=None, quantity=None, discount=None, currency=None, product=None,
            partner=None, taxes=None, move_type=None):
        self.ensure_one()
        return self.with_context(allss_nfe_import_tax_data=self.l10n_br_allss_import_nfe_tax).\
            _get_price_total_and_subtotal_model(
            price_unit=self.price_unit if price_unit is None else price_unit,
            quantity=self.quantity if quantity is None else quantity,
            discount=self.discount if discount is None else discount,
            currency=self.currency_id if currency is None else currency,
            product=self.product_id if product is None else product,
            partner=self.partner_id if partner is None else partner,
            taxes=self.tax_ids if taxes is None else taxes,
            move_type=self.move_id.move_type if move_type is None else move_type,
        )
