import logging

_logger = logging.getLogger(__name__)

from odoo import models, fields, api        #, tools
from num2words import num2words
from odoo.tools import html2plaintext


class ShippingNoteTml(models.Model):
    _inherit = 'account.move'

    extensive_value = fields.Char('Valor por Extenso')
    _allss_state_company = fields.Char('Sigla da UF da Empresa')
    _allss_state_partner = fields.Char('Sigla da UF do Parceiro')
    l10n_br_allss_legal_notes = fields.Text('Observações Legais')


    @api.onchange('invoice_line_ids')
    def add_legal_notes(self):
        notes = []
        for line in self.invoice_line_ids:
            _logger.info(f'Linha: {line.name}')
            for tax in line.tax_ids:
                _logger.info(f'Imposto: {tax.name} - {tax.invoice_legal_notes}')
                if tax.invoice_legal_notes:
                    plain_text = html2plaintext(tax.invoice_legal_notes).strip()
                    if plain_text and plain_text not in notes:
                        notes.append(plain_text)
                        _logger.info(f'Nota adicionada: {plain_text}')

        combined_notes = '\n'.join(notes)
        _logger.info(f'Notas combinadas finais: {combined_notes}')

        if self.l10n_br_allss_legal_notes != combined_notes:
            self.l10n_br_allss_legal_notes = combined_notes
            _logger.info(f'Campo atualizado com: {self.l10n_br_allss_legal_notes}')


                    

    
    def create_shipping_note(self):
        self.get_state(self.company_id.state_id.name, self.partner_id.state_id.name)
        val = self.amount_total
        val_ext = num2words(val, lang='pt_BR', to='currency')
        self.extensive_value = val_ext

        report = 'l10n_br_allss_shipping_note.action_shipping_note_report'
        # report = 'l10n_br_allss_shipping_note.print_shipping_note'
        return self.env.ref(report).report_action(self)  

    @api.model
    def get_state(self, st_co, st_pt):
        states = {
            'Acre':'AC','Alagoas':'AL','Amapá':'AP',
            'Amazonas':'AM','Bahia':'BA','Ceará':'CE',
            'Distrito Federal':'DF','Espírito Santo':'ES','Goiás':'GO',
            'Maranhão':'MA','Mato Grosso':'MT','Mato Grosso do Sul':'MS',
            'Minas Gerais':'MG','Pará':'PA','Paraíba':'PB',
            'Paraná':'PR','Pernambuco':'PE','Piauí':'PI',
            'Rio de Janeiro':'RJ','Rio Grande do Norte':'RN','Rio Grande do Sul':'RS',
            'Rondônia':'RO','Roraima':'RR','Santa Catarina':'SC',
            'São Paulo':'SP','Sergipe':'SE','Tocantins':'TO'
        }
        self.update({
            '_allss_state_partner': states.get(st_co),
            '_allss_state_company': states.get(st_pt)
        })

    
    def action_invoice_open(self):
        self.ensure_one()
        res = super(ShippingNoteTml, self).action_invoice_open()
        code_seq = self.service_serie_id.internal_sequence_id.code
        init_ref = 'INV'

        # if self.reference and self.reference[0:3] == init_ref and code_seq:
        if self.reference[0:3] == init_ref and code_seq != False:
            seq = self.env['ir.sequence'].next_by_code(f'{code_seq}')

            self.reference = seq
        return res