import zope.interface


class ICertificateProvider(zope.interface.Interface):
    def get_certificate(self, id, domains):
        """
        :param id: string
        :param domains: set
        :rtype: object with keys private_key, public_key and expires
        """
        pass
