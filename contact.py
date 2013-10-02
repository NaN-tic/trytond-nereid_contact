#This file is part nereid_contact module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from nereid.helpers import slugify, url_for
from nereid import render_template, request
from nereid.contrib.pagination import Pagination
from werkzeug.exceptions import NotFound

from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.pool import Pool

from email.mime.text import MIMEText
from email import Utils
from flask import jsonify

from .i18n import _

try:
    import emailvalid
    HAS_EMAILVALID = True
except ImportError:
    HAS_EMAILVALID = False

__all__ = ['Contact']


class Contact(ModelSQL, ModelView):
    'Contact'
    __name__ = 'nereid.contact'
    _rec_name = 'address'

    per_page = 10

    address = fields.Many2One('party.address', 'Contact', required=True)
    uri = fields.Char('URI', required=True,
        help='Unique name is used as the uri.')
    description = fields.Text('Description',
        help='Allow HTML in description contact')
    status = fields.Boolean('Status',
        help='Dissable to not show contact')
    send_email = fields.Boolean('Send Email',
        help='Show a form to send a email to address')
    smtp_server = fields.Many2One('smtp.server', 'SMTP Server',
        states={
            'invisible': ~Eval('send_email', True),
        }, 
        domain=[('state', '=', 'done')],
        help='Force SMTP server or use global defined in Nereid Website')
    show_street = fields.Boolean('Show Street')
    show_phone = fields.Boolean('Show Phone')
    show_fax = fields.Boolean('Show Fax')
    show_email = fields.Boolean('Show Email')

    @staticmethod
    def default_status():
        return True

    @staticmethod
    def default_show_street():
        return True

    @staticmethod
    def default_show_phone():
        return True

    @staticmethod
    def default_show_fax():
        return True

    @classmethod
    def __setup__(cls):
        super(Contact, cls).__setup__()
        cls._sql_constraints += [
            ('uri', 'UNIQUE(uri)',
                'The Unique Name of the Contact must be unique.'),
            ]
        cls._error_messages.update({
            'delete_contacts': ('You can not delete '
                'contacts because you will get error 404 NOT Found. '
                'Dissable active field.'),
            })

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for values in vlist:
            values['uri'] = slugify(values.get('uri'))
        return super(Contact, cls).create(vlist)

    @classmethod
    def write(cls, contacts, vals):
        vals = vals.copy()
        if vals.get('uri'):
            vals['uri'] = slugify(vals.get('uri'))
        super(Contact, cls).write(contacts, vals)

    @classmethod
    def copy(cls, contacts, default=None):
        new_contacts = []
        for contact in contacts:
            default['uri'] = '%s-copy' % contact.uri
            new_contact, = super(Contact, cls).copy([contact], default=default)
            new_contacts.append(new_contact)
        return new_contacts

    @classmethod
    def delete(cls, categories):
        cls.raise_user_error('delete_contacts')

    @classmethod
    def all(cls):
        """
        Render all contacts
        """
        Contact = Pool().get('nereid.contact')

        page = request.args.get('page', 1, int)
        clause = []
        clause.append(('status', '=', True))

        contacts = Pagination(
            Contact, clause, page, cls.per_page
        )

        return render_template('contact-all.jinja', contacts=contacts)

    @classmethod
    def render(cls, uri):
        """
        Render contact
        """
        try:
            contact, = cls.search([('uri', '=', uri)])
        except ValueError:
            return NotFound()

        if request.method == 'POST':
            if not contact.send_email or not contact.address.email:
                return False

            contact_name = contact.address.name or contact.address.party.name

            values = {}
            for data in request.json:
                values[data['name']] = data['value']

            if not values.get('email', False):
                return False

            if HAS_EMAILVALID:
                if not emailvalid.check_email(values.get('email')):
                    return False

            vals = []
            for key, val in values.items():
                vals.append('%s: %s' % (key, val))

            server = request.nereid_website.smtp_server
            if contact.smtp_server:
                server = contact.smtp_server

            from_ = server.smtp_email
            to_ = server.smtp_email
            subject = _("Contact %(name)s", name=contact_name)
            msg_intro = _("Contact details from %(website)s", 
                website=request.nereid_website.company.party.name)
            msg_signature = _("Regards\n%(company)s", 
                company=request.nereid_website.company.party.name)
            details = '\n'.join(vals)
            body = '%(intro)s\n\n%(details)s\n\n%(signature)s' % {
                'intro': msg_intro,
                'details': details.encode("UTF-8"),
                'signature': msg_signature,
                }

            msg = MIMEText(body, 'plain')
            msg['Subject'] = values.get('subject', subject)
            msg['From'] = from_
            msg['To'] = from_
            msg['Reply-to'] = values.get('email')
            msg['Message-ID'] = Utils.make_msgid()

            try:
                SMTP = Pool().get('smtp.server')
                server = SMTP.get_smtp_server(server)
                server.sendmail(from_, to_, msg.as_string())
                server.quit()
                return jsonify(result=True)
            except:
                return jsonify(result=False)

        return render_template('contact.jinja', contact=contact)

    def get_absolute_url(self, **kwargs):
        return url_for(
            'nereid.contact.render', uri=self.uri, **kwargs
        )
