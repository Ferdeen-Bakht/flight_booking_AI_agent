const NAME = /^[A-Za-z][A-Za-z '\-]{0,49}$/;

export const blankPassenger = () => ({
  title: "mr", gender: "m", given_name: "", family_name: "", born_on: "",
  passport_number: "", passport_country: "PK", passport_expiry: "",
});

/** Returns an array of error strings (empty = valid). Mirrors the server-side checks. */
export function validatePassenger(p, i, passportRequired, lastDeparture) {
  const who = `Passenger ${i + 1}`;
  const e = [];
  if (!NAME.test(p.given_name.trim())) e.push(`${who}: first name must use letters only.`);
  if (!NAME.test(p.family_name.trim())) e.push(`${who}: last name must use letters only.`);
  const born = new Date(p.born_on);
  if (!p.born_on || isNaN(born)) e.push(`${who}: enter date of birth.`);
  else {
    const age = (Date.now() - born) / 31557600000;
    if (born >= new Date() || age > 120) e.push(`${who}: date of birth looks wrong.`);
    else if (age < 12) e.push(`${who}: must be 12 or older (adult fare).`);
  }
  if (passportRequired || p.passport_number) {
    if (!/^[A-Za-z0-9]{6,12}$/.test(p.passport_number.trim())) e.push(`${who}: passport number must be 6-12 letters/digits.`);
    if (!/^[A-Za-z]{2}$/.test(p.passport_country.trim())) e.push(`${who}: passport country must be a 2-letter code.`);
    if (!p.passport_expiry || new Date(p.passport_expiry) <= new Date(lastDeparture.slice(0, 10)))
      e.push(`${who}: passport must be valid beyond the trip.`);
  }
  return e;
}

export const validateContact = (c) => {
  const e = [];
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(c.email)) e.push("Enter a valid contact email.");
  if (!/^\+\d{8,15}$/.test(c.phone)) e.push("Phone must be international format, e.g. +923001234567.");
  return e;
};
