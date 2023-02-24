FROM jbergknoff/postgresql-client

FROM php:apache

RUN apt-get update
RUN apt-get -y install nano wget

##RUN wget https://security.debian.org/debian-security/pool/updates/main/p/postgresql-11/libpq5_11.14-0+deb10u1_amd64.deb
#RUN dpkg -i libpq5_11.14-0+deb10u1_amd64.deb
#RUN wget https://security.debian.org/debian-security/pool/updates/main/p/postgresql-11/libpq-dev_11.14-0+deb10u1_amd64.deb
#RUN dpkg -i libpq-dev_11.14-0+deb10u1_amd64.deb
#RUN wget https://debian-security.mirror.ate.info/pool/updates/main/p/postgresql-11/libpq-dev_11.16-0+deb10u1_amd64.deb
#RUN dpkg -i libpq-dev_11.16-0+deb10u1_amd64.deb

RUN apt-get update && apt-get install -y libpq-dev && docker-php-ext-install pdo pdo_pgsql

RUN docker-php-ext-configure pgsql -with-pgsql=/usr/local/pgsql \
    && docker-php-ext-install pgsql pdo_pgsql
  
RUN a2enmod ssl && a2enmod rewrite

COPY ./000-default.conf /etc/apache2/sites-available/000-default.conf

# RUN apt-get install -y
COPY --from=mlocati/php-extension-installer /usr/bin/install-php-extensions /usr/local/bin/


RUN mv $PHP_INI_DIR/php.ini-development $PHP_INI_DIR/php.ini
# COPY ./php.ini $PHP_INI_DIR/php.ini
COPY ./php.ini $PHP_INI_DIR/conf.d/
COPY . /var/www/html/
WORKDIR /var/www/html/
RUN service apache2 restart
# Use the default production configuration
EXPOSE 80
EXPOSE 443
